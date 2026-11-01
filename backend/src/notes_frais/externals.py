"""Personnes extérieures (notes-de-frais.md §7 quater) : un prof invité, un
intervenant, payé par une note de frais ou des honoraires sans être membre.

Le module les range dans `nf_externals` et leur donne un person_id négatif
(-id), pour qu'elles passent partout où passe une personne : « Pour qui ? »,
RIB, notes, Docs, mail quand c'est payé. Les membres viennent de l'annuaire
de l'hôte, les extérieurs s'y ajoutent après.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import External
from .ports import Annuaire, Organisation, Personne

ROLE = "extérieur"


def person_id(external_id: int) -> int:
    return -external_id


def is_external(person_id: int) -> bool:
    return person_id < 0


def personne(external: External) -> Personne:
    return Personne(-external.id, external.name, (external.email,) if external.email else (), None, ROLE)


@dataclass(frozen=True)
class WithExternals:
    """L'annuaire de l'hôte, plus les extérieurs de l'organisation."""

    members: Annuaire

    def personnes(self, db: Session, org_id: int, person_ids: set[int]) -> dict[int, Personne]:
        trouvees = self.members.personnes(db, org_id, {i for i in person_ids if not is_external(i)})
        ids = [-i for i in person_ids if is_external(i)]
        if ids:
            for external in db.scalars(select(External).where(External.org_id == org_id, External.id.in_(ids))):
                trouvees[-external.id] = personne(external)
        return trouvees

    def tresoriers(self, db: Session, org_id: int) -> list[Personne]:
        return self.members.tresoriers(db, org_id)

    def toutes(self, db: Session, org_id: int, le: date | None = None) -> list[Personne]:
        """Les membres d'abord, puis les extérieurs encore dans la liste."""
        externals = db.scalars(
            select(External).where(External.org_id == org_id, External.removed_at.is_(None)).order_by(External.name)
        )
        return self.members.toutes(db, org_id, le) + [personne(e) for e in externals]

    def organisation(self, db: Session, org_id: int) -> Organisation:
        return self.members.organisation(db, org_id)
