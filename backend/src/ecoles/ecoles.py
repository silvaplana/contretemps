"""Logique métier des écoles (voir spec/SPEC.md §2.3 et §6.1) — aucune
dépendance FastAPI ici, juste des méthodes appelées par receiver.py.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Ecole


def normaliser_iban(iban: str | None) -> str | None:
    """« fr76 3000 6000 0112 3456 7890 189 » -> « FR7630006000011234567890189 » ;
    vide -> None. Lève ValueError si la forme ou la clé de contrôle (norme
    ISO 13616, reste 1 modulo 97) ne va pas."""
    texte = "".join((iban or "").split()).upper()
    if not texte:
        return None
    if not (15 <= len(texte) <= 34 and texte[:2].isalpha() and texte[2:4].isdigit() and texte.isalnum()):
        raise ValueError("Cet IBAN n'a pas la bonne forme (ex. FR76 3000 6000 0112 3456 7890 189).")
    nombre = "".join(str(int(c, 36)) for c in texte[4:] + texte[:4])
    if int(nombre) % 97 != 1:
        raise ValueError("Cet IBAN est incorrect : vérifiez-le, un caractère est sans doute mal recopié.")
    return texte


def normaliser_siret(siret: str | None) -> str | None:
    """« 123 456 789 00012 » -> « 12345678900012 » ; vide -> None. Lève
    ValueError si ce ne sont pas 14 chiffres (spec §6.1)."""
    chiffres = "".join((siret or "").split())
    if not chiffres:
        return None
    if not (chiffres.isdigit() and len(chiffres) == 14):
        raise ValueError("Le SIRET doit compter 14 chiffres.")
    return chiffres


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
        """Lève ValueError (message montrable) pour un SIRET invalide."""
        ecole = self.get(db, ecole_id)
        if ecole is None:
            return None
        if "siret" in champs:
            champs["siret"] = normaliser_siret(champs["siret"])
        if "iban" in champs:
            champs["iban"] = normaliser_iban(champs["iban"])
        for cle in ("adresse", "ville"):
            if cle in champs:
                champs[cle] = (champs[cle] or "").strip() or None
        # `champs` ne contient déjà que les champs explicitement fournis
        # (exclude_unset=True côté receiver) — un `if valeur is not None`
        # ici empêchait à tort de vider un champ nullable.
        for cle, valeur in champs.items():
            setattr(ecole, cle, valeur)
        db.commit()
        db.refresh(ecole)
        return ecole
