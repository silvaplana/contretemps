"""Logique métier des professeurs (voir spec/SPEC.md §6.3 : "aucun champ
supplémentaire propre pour l'instant" — pas de models.py dans ce module,
juste `Comptes` (champs communs) + `CoursService` (cours enseignés,
relation, voir §6.5) réutilisés tels quels.
"""

from __future__ import annotations

from comptes import Compte, Comptes
from cours import CoursService
from sqlalchemy.orm import Session


class Profs:
    def __init__(self, comptes: Comptes, cours: CoursService) -> None:
        self.comptes = comptes
        self.cours = cours

    def list(self, db: Session, ecole_id: int) -> list[Compte]:
        return self.comptes.list_par_role(db, ecole_id, role="professeur")

    def get(self, db: Session, prof_id: int) -> Compte | None:
        compte = self.comptes.get(db, prof_id)
        if compte is None or compte.role != "professeur":
            return None
        return compte

    def create(
        self,
        db: Session,
        ecole_id: int,
        nom: str,
        prenom: str,
        email: str | None = None,
        telephone: str | None = None,
    ) -> Compte:
        return self.comptes.create(
            db, ecole_id=ecole_id, role="professeur", nom=nom, prenom=prenom, email=email,
            telephone=telephone,
        )

    def update(self, db: Session, prof_id: int, **champs) -> Compte | None:
        if self.get(db, prof_id) is None:
            return None
        return self.comptes.update(db, prof_id, **champs)

    def delete(self, db: Session, prof_id: int) -> bool:
        if self.get(db, prof_id) is None:
            return False
        # Retire le prof de tous ses cours avant de supprimer le compte
        # (voir cours.py : table de jointure cours_professeurs).
        for c in self.cours.cours_du_professeur(db, prof_id):
            self.cours.retirer_professeur(db, c.id, prof_id)
        return self.comptes.delete(db, prof_id)
