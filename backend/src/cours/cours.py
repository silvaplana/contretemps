"""Logique métier des cours (voir spec/SPEC.md §5.1.4 et §6.5)."""

from __future__ import annotations

from comptes import Compte
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Cours, cours_professeurs, eleves_cours


class CoursService:
    def list(self, db: Session, ecole_id: int) -> list[Cours]:
        return list(db.scalars(select(Cours).where(Cours.ecole_id == ecole_id)))

    def get(self, db: Session, cours_id: int) -> Cours | None:
        return db.get(Cours, cours_id)

    def create(self, db: Session, ecole_id: int, nom: str, **champs) -> Cours:
        cours = Cours(ecole_id=ecole_id, nom=nom, **champs)
        db.add(cours)
        db.commit()
        db.refresh(cours)
        return cours

    def update(self, db: Session, cours_id: int, **champs) -> Cours | None:
        cours = self.get(db, cours_id)
        if cours is None:
            return None
        # `champs` ne contient déjà que les champs explicitement fournis
        # (exclude_unset=True côté receiver) — un `if valeur is not None`
        # ici empêchait à tort de vider un champ nullable.
        for cle, valeur in champs.items():
            setattr(cours, cle, valeur)
        db.commit()
        db.refresh(cours)
        return cours

    def delete(self, db: Session, cours_id: int) -> bool:
        cours = self.get(db, cours_id)
        if cours is None:
            return False
        db.delete(cours)
        db.commit()
        return True

    # --- Relations (voir §6.5 : tables de jointure, rien stocké sur Cours) ---

    def ajouter_professeur(self, db: Session, cours_id: int, professeur_id: int) -> None:
        exists = db.execute(
            select(cours_professeurs).where(
                cours_professeurs.c.cours_id == cours_id,
                cours_professeurs.c.professeur_id == professeur_id,
            )
        ).first()
        if exists is None:
            db.execute(cours_professeurs.insert().values(cours_id=cours_id, professeur_id=professeur_id))
            db.commit()

    def retirer_professeur(self, db: Session, cours_id: int, professeur_id: int) -> None:
        db.execute(
            cours_professeurs.delete().where(
                cours_professeurs.c.cours_id == cours_id,
                cours_professeurs.c.professeur_id == professeur_id,
            )
        )
        db.commit()

    def professeurs_du_cours(self, db: Session, cours_id: int) -> list[Compte]:
        return list(
            db.scalars(
                select(Compte)
                .join(cours_professeurs, cours_professeurs.c.professeur_id == Compte.id)
                .where(cours_professeurs.c.cours_id == cours_id)
            )
        )

    def inscrire_eleve(self, db: Session, cours_id: int, eleve_id: int) -> None:
        exists = db.execute(
            select(eleves_cours).where(
                eleves_cours.c.cours_id == cours_id, eleves_cours.c.eleve_id == eleve_id
            )
        ).first()
        if exists is None:
            db.execute(eleves_cours.insert().values(cours_id=cours_id, eleve_id=eleve_id))
            db.commit()

    def desinscrire_eleve(self, db: Session, cours_id: int, eleve_id: int) -> None:
        db.execute(
            eleves_cours.delete().where(
                eleves_cours.c.cours_id == cours_id, eleves_cours.c.eleve_id == eleve_id
            )
        )
        db.commit()

    def eleves_du_cours(self, db: Session, cours_id: int) -> list[Compte]:
        return list(
            db.scalars(
                select(Compte)
                .join(eleves_cours, eleves_cours.c.eleve_id == Compte.id)
                .where(eleves_cours.c.cours_id == cours_id)
            )
        )

    def cours_du_professeur(self, db: Session, professeur_id: int) -> list[Cours]:
        """Utilisé pour le sélecteur de cours d'un prof (§4) et pour
        Présence (§5.2)."""
        return list(
            db.scalars(
                select(Cours)
                .join(cours_professeurs, cours_professeurs.c.cours_id == Cours.id)
                .where(cours_professeurs.c.professeur_id == professeur_id)
            )
        )

    def cours_de_leleve(self, db: Session, eleve_id: int) -> list[Cours]:
        return list(
            db.scalars(
                select(Cours)
                .join(eleves_cours, eleves_cours.c.cours_id == Cours.id)
                .where(eleves_cours.c.eleve_id == eleve_id)
            )
        )
