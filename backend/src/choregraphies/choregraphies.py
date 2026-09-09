"""Logique métier des chorégraphies (voir spec/SPEC.md §6.7). Dépend de
`cours` : seuls les élèves déjà inscrits au cours lié peuvent être ajoutés
à une chorégraphie de ce cours — jamais l'inverse.
"""

from __future__ import annotations

from comptes import Compte
from cours import CoursService
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Choregraphie, choregraphies_eleves


class Choregraphies:
    def __init__(self, cours: CoursService) -> None:
        self.cours = cours

    def list(self, db: Session, cours_id: int) -> list[Choregraphie]:
        return list(
            db.scalars(select(Choregraphie).where(Choregraphie.cours_id == cours_id))
        )

    def get(self, db: Session, choregraphie_id: int) -> Choregraphie | None:
        return db.get(Choregraphie, choregraphie_id)

    def create(self, db: Session, cours_id: int, nom: str, **champs) -> Choregraphie:
        choregraphie = Choregraphie(cours_id=cours_id, nom=nom, **champs)
        db.add(choregraphie)
        db.commit()
        db.refresh(choregraphie)
        return choregraphie

    def update(self, db: Session, choregraphie_id: int, **champs) -> Choregraphie | None:
        choregraphie = self.get(db, choregraphie_id)
        if choregraphie is None:
            return None
        # `champs` ne contient déjà que les champs explicitement fournis
        # (exclude_unset=True côté receiver) — un `if valeur is not None`
        # ici empêchait à tort de vider un champ nullable.
        for cle, valeur in champs.items():
            setattr(choregraphie, cle, valeur)
        db.commit()
        db.refresh(choregraphie)
        return choregraphie

    def delete(self, db: Session, choregraphie_id: int) -> bool:
        choregraphie = self.get(db, choregraphie_id)
        if choregraphie is None:
            return False
        db.execute(
            choregraphies_eleves.delete().where(
                choregraphies_eleves.c.choregraphie_id == choregraphie_id
            )
        )
        db.delete(choregraphie)
        db.commit()
        return True

    # --- Élèves participants ---

    def ajouter_eleve(self, db: Session, choregraphie_id: int, eleve_id: int) -> bool:
        """Refuse un élève qui n'est pas inscrit au cours lié (voir §6.7)."""
        choregraphie = self.get(db, choregraphie_id)
        if choregraphie is None:
            return False
        inscrits = {e.id for e in self.cours.eleves_du_cours(db, choregraphie.cours_id)}
        if eleve_id not in inscrits:
            return False
        exists = db.execute(
            select(choregraphies_eleves).where(
                choregraphies_eleves.c.choregraphie_id == choregraphie_id,
                choregraphies_eleves.c.eleve_id == eleve_id,
            )
        ).first()
        if exists is None:
            db.execute(
                choregraphies_eleves.insert().values(
                    choregraphie_id=choregraphie_id, eleve_id=eleve_id
                )
            )
            db.commit()
        return True

    def retirer_eleve(self, db: Session, choregraphie_id: int, eleve_id: int) -> None:
        db.execute(
            choregraphies_eleves.delete().where(
                choregraphies_eleves.c.choregraphie_id == choregraphie_id,
                choregraphies_eleves.c.eleve_id == eleve_id,
            )
        )
        db.commit()

    def eleves_participants(self, db: Session, choregraphie_id: int) -> list[Compte]:
        return list(
            db.scalars(
                select(Compte)
                .join(choregraphies_eleves, choregraphies_eleves.c.eleve_id == Compte.id)
                .where(choregraphies_eleves.c.choregraphie_id == choregraphie_id)
            )
        )
