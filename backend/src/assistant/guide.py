"""Le guide de l'appli pour l'assistant (spec/modules/assistant-ia.md §6) :
un seul outil de lecture qui rend le plan des écrans d'un module (son
`guide.md`, déclaré dans son module.py), pour dire où est chaque bouton.
Seulement les modules allumés dans l'école, et dont la personne a les droits.
"""

from __future__ import annotations

from collections.abc import Callable

from comptes import roles
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .actions import Action
from .modifications import Refus


class Guide(BaseModel):
    module: str | None = Field(default=None, description="Nom du module (ex. « Financier »), ou null pour la liste des modules.")


def guide_action(modules: list, disabled: Callable[[Session, int], set[str]]) -> Action:
    avec_guide = [m for m in modules if m.guide]

    def visibles(db: Session, compte, org_id: int) -> list:
        off = disabled(db, org_id)
        return [m for m in avec_guide if m.key not in off and all(roles.has_right(compte, r.key) for r in m.rights)]

    def read(db: Session, compte, org_id: int, p: Guide) -> str:
        mods = visibles(db, compte, org_id)
        noms = ", ".join(m.label for m in mods) or "aucun"
        if p.module is None:
            return f"Modules avec un guide : {noms}."
        cherche = p.module.strip().casefold()
        for m in mods:
            if cherche in (m.key.casefold(), m.label.casefold()):
                return f"Guide du module {m.label}\n\n{m.guide}"
        raise Refus(f"pas de guide pour « {p.module} ». Modules avec un guide : {noms}")

    description = (
        "Le plan des écrans d'un module : où est chaque onglet, puce, bouton et menu ⋯, et ses règles. Lis-le avant de dire "
        "à la personne où cliquer ; ne décris jamais un écran de mémoire. Modules : "
        + ", ".join(m.label for m in avec_guide) + "."
    )
    return Action("app_guide", "Guide", description, Guide, None, admin_only=False, read=read)
