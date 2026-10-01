"""Logique métier des écoles (voir spec/SPEC.md §2.3 et §6.1) — aucune
dépendance FastAPI ici, juste des méthodes appelées par receiver.py.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Ecole


class Ecoles:
    def list(self, db: Session) -> list[Ecole]:
        return list(db.scalars(select(Ecole)))

    def get(self, db: Session, ecole_id: int) -> Ecole | None:
        return db.get(Ecole, ecole_id)

    def find_by_nom_code_postal(self, db: Session, nom: str, code_postal: str) -> Ecole | None:
        """Le couple (nom, code_postal) identifie une école de façon unique
        (voir §6.1) — utilisé au login pour savoir dans quelle école un
        compte doit être recherché."""
        return db.scalar(
            select(Ecole).where(Ecole.nom == nom, Ecole.code_postal == code_postal)
        )

    def create(
        self,
        db: Session,
        nom: str,
        code_postal: str,
    ) -> Ecole:
        ecole = Ecole(nom=nom, code_postal=code_postal)
        db.add(ecole)
        db.commit()
        db.refresh(ecole)
        return ecole

    def update(self, db: Session, ecole_id: int, **champs) -> Ecole | None:
        ecole = self.get(db, ecole_id)
        if ecole is None:
            return None
        # `champs` ne contient déjà que les champs explicitement fournis
        # (exclude_unset=True côté receiver) — un `if valeur is not None`
        # ici empêchait à tort de vider un champ nullable.
        for cle, valeur in champs.items():
            setattr(ecole, cle, valeur)
        db.commit()
        db.refresh(ecole)
        return ecole
