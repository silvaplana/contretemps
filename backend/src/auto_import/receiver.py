"""Routes de l'écran Financier › Pièces › ⋯ › Import auto pièces
(spec/modules/import-auto-pieces.md §3, §4) : trésoriers et Super User
seulement (Accès au Financier). Sous-module éteint : « introuvable »."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_db

from .models import AutoImportRule
from .service import AutoImport


class RuleIn(BaseModel):
    name: str = Field("Nouvel import", min_length=1, max_length=30)
    active: bool = True
    season_id: int | None = None
    nature: Literal["achat", "vente", "frais", "honoraires"] = "achat"
    source_kind: Literal["docs", "drive", "mail", "helloasso"] = "docs"
    source_ref: int | None = None
    source_path: str = Field("", max_length=1000)
    target_kind: Literal["none", "docs", "drive"] = "none"
    target_ref: int | None = None
    target_path: str = Field("", max_length=1000)
    frequency: Literal["hourly", "daily", "weekly", "monthly"] = "daily"
    at_time: str = Field("07:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    created_status: Literal["a_valider"] = "a_valider"
    mail_senders: str = Field("", max_length=500)
    mail_words: str = Field("", max_length=500)
    mail_need_amount: bool = True
    helloasso_accounts: dict[str, int | None] = Field(default_factory=dict)


class RuleOut(RuleIn):
    id: int
    pieces: int
    last_run_at: datetime | None
    last_message: str


FIELDS = list(RuleIn.model_fields)


def _out(rule: AutoImportRule, pieces: int) -> RuleOut:
    return RuleOut(id=rule.id, pieces=pieces, last_run_at=rule.last_run_at, last_message=rule.last_message,
                   **{k: getattr(rule, k) for k in FIELDS})


class AutoImportReceiver:
    def __init__(
        self, client: AutoImport, app: FastAPI, membre_courant: Callable, places: Callable, formulas: Callable,
    ) -> None:
        self.client = client
        # (db, org_id, season_id) → les formules de la campagne HelloAsso.
        self.formulas = formulas
        # (db, org_id) → sources et destinations possibles (drives, boîtes, saisons).
        self.places = places
        self._routes(app, membre_courant)

    def _rule(self, db: Session, membre, rule_id: int) -> AutoImportRule:
        try:
            return self.client.rule(db, membre.org_id, rule_id)
        except LookupError:
            raise HTTPException(status_code=404, detail="Import introuvable") from None

    def _routes(self, app: FastAPI, membre_courant: Callable) -> None:  # noqa: C901 - une fonction par route
        client, db_dep = self.client, Depends(get_db)

        def tresorier(m=Depends(membre_courant)):
            if not (m.est_tresorier or m.est_superuser):
                raise HTTPException(status_code=403, detail="Réservé à l'Accès au Financier")
            return m

        membre = Depends(tresorier)
        base = "/auto-import"

        @app.get(base)
        def listing(db: Session = db_dep, m=membre):
            counts = client.counts(db, m.org_id)
            return {"rules": [_out(r, counts.get(r.id, 0)) for r in client.rules(db, m.org_id)], **self.places(db, m.org_id)}

        @app.post(base, response_model=RuleOut)
        def create(data: RuleIn | None = None, db: Session = db_dep, m=membre):
            rule = AutoImportRule(organization_id=m.org_id, created_by=m.agissant_id or m.person_id)
            for k, v in (data or RuleIn()).model_dump().items():
                setattr(rule, k, v)
            db.add(rule)
            db.commit()
            return _out(rule, 0)

        @app.put(f"{base}/{{rule_id}}", response_model=RuleOut)
        def update(rule_id: int, data: RuleIn, db: Session = db_dep, m=membre):
            if data.source_kind == "mail" and data.target_kind == "none":
                raise HTTPException(status_code=422, detail="Une boîte mail demande une destination")
            rule = self._rule(db, m, rule_id)
            for k, v in data.model_dump().items():
                setattr(rule, k, v)
            db.commit()
            return _out(rule, client.counts(db, m.org_id).get(rule.id, 0))

        @app.delete(f"{base}/{{rule_id}}", status_code=204)
        def delete(rule_id: int, db: Session = db_dep, m=membre):
            self._rule(db, m, rule_id)
            client.delete(db, m.org_id, rule_id)

        @app.post(f"{base}/{{rule_id}}/run")
        def run(rule_id: int, db: Session = db_dep, m=membre):
            """« Regarder maintenant » (§4)."""
            rule = self._rule(db, m, rule_id)
            created = client.run(db, rule)
            return {"created": created, "message": rule.last_message}

        @app.get(f"{base}/{{rule_id}}/pieces")
        def pieces(rule_id: int, db: Session = db_dep, m=membre):
            """« Voir » (§3) : les pièces créées par cet import."""
            from notes_frais.models import NoteFrais

            rule = self._rule(db, m, rule_id)
            ids = client.note_ids(db, rule)
            notes = list(db.scalars(select(NoteFrais).where(NoteFrais.id.in_(ids), NoteFrais.org_id == m.org_id)))
            notes.sort(key=lambda n: ids.index(n.id))
            return {"notes": client.notes.notes_dicts(db, m, notes)}

        @app.get("/auto-import-helloasso")
        def helloasso(season_id: int | None = None, db: Session = db_dep, m=membre):
            """Source HelloAsso (§4.2) : les formules de la campagne et les
            comptes de produits où les envoyer."""
            accounts = client.notes.categories(db, m.org_id, ventes=True)
            return {
                "formulas": self.formulas(db, m.org_id, season_id),
                "accounts": [{"id": c.id, "libelle": c.libelle, "code": c.code} for c in accounts],
            }

        @app.get("/auto-import-docs-folders")
        def docs_folders(parent: int | None = None, db: Session = db_dep, m=membre):
            """Les dossiers de Docs (Public et Privé), pour choisir une source
            ou une destination."""
            from documents.models import KIND_FOLDER, DocNode

            query = select(DocNode).where(
                DocNode.org_id == m.org_id, DocNode.kind == KIND_FOLDER, DocNode.deleted_at.is_(None),
                DocNode.space.in_(("public", "private")),
            )
            query = query.where(DocNode.parent_id == parent) if parent else query.where(DocNode.parent_id.is_(None))
            return [{"id": n.id, "name": n.name, "space": n.space} for n in db.scalars(query.order_by(DocNode.name))]
