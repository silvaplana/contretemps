"""La campagne HelloAsso d'une saison (spec/modules/helloasso.md §3) : le
formulaire choisi impose ses questions comme champs de la fiche des membres,
verrouillés (`member_fields.source = "helloasso"`). Changer de campagne
retire les champs de l'ancienne (réponses gardées) ; « Nos champs » les
retire tous."""

from __future__ import annotations

from collections.abc import Callable

from members import fields as member_fields
from securite.chiffrement import dechiffrer
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import api
from .connection import Connection
from .models import OrgHelloAsso, SeasonHelloAsso

SOURCE = "helloasso"


class Campaigns:
    def __init__(
        self,
        forms: Callable[[str, str, str], list[api.Form]] = api.forms,
        form_fields: Callable[[str, str, str, str, str], list[dict]] = api.form_fields,
        form_prices: Callable[[str, str, str, str, str], dict] = api.form_prices,
    ) -> None:
        # Remplaçables dans les tests (pas d'appel réseau).
        self.forms = forms
        self.form_fields = form_fields
        self.form_prices = form_prices

    @staticmethod
    def _keys(connection: OrgHelloAsso) -> tuple[str, str, str]:
        secret = dechiffrer(connection.secret_encrypted)
        if secret is None:
            raise api.HelloAssoError("Les clés enregistrées ne se lisent plus : changez les clés.")
        return connection.client_id, secret, connection.org_slug

    @staticmethod
    def current(db: Session, season_id: int) -> SeasonHelloAsso | None:
        return db.scalar(select(SeasonHelloAsso).where(SeasonHelloAsso.season_id == season_id))

    def list_forms(self, db: Session, org_id: int) -> list[api.Form]:
        connection = Connection.row(db, org_id)
        if connection is None or not connection.active:
            return []
        return self.forms(*self._keys(connection))

    def choose(self, db: Session, org_id: int, season_id: int, form_type: str, form_slug: str) -> SeasonHelloAsso:
        """Lit le formulaire, met ses questions sur la fiche de la saison et
        le garde comme campagne (sans commit)."""
        connection = Connection.row(db, org_id)
        if connection is None or not connection.active:
            raise api.HelloAssoError("HelloAsso n’est pas connecté.")
        keys = self._keys(connection)
        form = next((f for f in self.forms(*keys) if (f.form_type, f.form_slug) == (form_type, form_slug)), None)
        if form is None:
            raise api.HelloAssoError("Cette campagne n’existe plus sur HelloAsso.")
        member_fields.set_external(db, org_id, season_id, SOURCE, self.form_fields(*keys, form_type, form_slug))
        row = self.current(db, season_id) or SeasonHelloAsso(org_id=org_id, season_id=season_id)
        row.form_type, row.form_slug, row.form_name = form.form_type, form.form_slug, form.name
        db.add(row)
        db.flush()
        return row

    def clear(self, db: Session, org_id: int, season_id: int) -> None:
        """« Nos champs » : plus de campagne ; ses champs quittent la fiche,
        leurs réponses restent (sans commit)."""
        member_fields.set_external(db, org_id, season_id, SOURCE, [])
        row = self.current(db, season_id)
        if row is not None:
            db.delete(row)
        db.flush()

    def prices(self, db: Session, org_id: int, season_id: int) -> dict | None:
        """Les tarifs de la campagne de la saison (spec §3, `core.md` §9.3),
        en lecture seule : formules et options lues sur HelloAsso, codes
        promo vus dans les commandes synchronisées. None sans campagne."""
        from sqlalchemy import func

        from .models import HelloAssoRegistration

        row = self.current(db, season_id)
        if row is None:
            return None
        connection = Connection.row(db, org_id)
        if connection is None or not connection.active:
            raise api.HelloAssoError("HelloAsso n’est pas connecté.")
        prices = self.form_prices(*self._keys(connection), row.form_type, row.form_slug)
        codes = db.execute(
            select(HelloAssoRegistration.discount_code, func.count())
            .where(
                HelloAssoRegistration.season_id == season_id,
                HelloAssoRegistration.discount_code.is_not(None),
                HelloAssoRegistration.gone_at.is_(None),
            )
            .group_by(HelloAssoRegistration.discount_code)
            .order_by(HelloAssoRegistration.discount_code)
        ).all()
        return {"form_name": row.form_name, **prices, "codes": [{"code": c, "uses": n} for c, n in codes]}
