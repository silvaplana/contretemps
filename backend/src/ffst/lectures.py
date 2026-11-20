"""The FFST lists opened to the assistant (Seb, 20 November 2026), in
reading only: the copy of the last reading of the federation's site, as
the FFST tab shows it. Nothing here reads the site again or acts on it
(requests, « Rafraîchir »): that stays on screen."""

from __future__ import annotations

import json

from assistant.actions import Action
from comptes import rbac
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .receiver import FfstReceiver
from .site import LISTS

LIMIT_MAX = 300
# The columns of the FFST tab (FfstOnglet.jsx), as the site names them.
COLUMNS = {"name": "Nom et Prénom", "born": "Né(e) le", "nature": "Type", "licence": "Licence n°",
           "requested": "Demandé le ", "request": "IDDemande", "state": "Etat"}


class Licences(BaseModel):
    list: str | None = Field(default=None, description="drafts (Brouillons), validated (Validées), licensees (Licenciés), ou null pour les trois.")
    text: str | None = Field(default=None, description="Bout de nom ou prénom, ou null.")
    limit: int = Field(default=100, ge=1, le=LIMIT_MAX, description="Lignes au plus par liste.")


def lectures(receiver: FfstReceiver) -> list[Action]:
    def read(db: Session, compte, org_id: int, p: Licences) -> str:
        rbac.require_admin(compte, org_id)
        out = receiver.listes(org_id, db=db)
        if not out.connected:
            return json.dumps({"connected": False})
        text = (p.text or "").casefold().strip()
        lists = {}
        for name in LISTS:
            if p.list and p.list != name:
                continue
            rows = [
                {key: row.get(column) for key, column in COLUMNS.items() if row.get(column) not in (None, "")}
                for row in out.lists.get(name, [])
                if text in (row.get(COLUMNS["name"]) or "").casefold()
            ]
            lists[name] = {"count": len(rows), "lines": rows[: p.limit]}
        return json.dumps({"connected": True, "readAt": out.read_at, "lists": lists},
                          ensure_ascii=False, separators=(",", ":"), default=str)

    return [
        Action(
            name="ffst_licences",
            module="FFST",
            description="Onglet FFST : les Brouillons (panier), les demandes Validées à payer et les Licenciés de la "
            "saison, tels que lus la dernière fois sur le site de la FFST (« Lu à … »). Lecture seule : demander "
            "ou supprimer une licence et Rafraîchir se font à l'écran.",
            params=Licences,
            prepare=None,
            read=read,
        ),
    ]
