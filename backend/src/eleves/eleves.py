"""Logique métier des élèves (voir spec/SPEC.md §6.4). S'appuie sur
`comptes` pour les champs communs (nom/prénom/email...) — ne les duplique
pas, ne fait qu'ajouter `ProfilEleve`/`ContactEleve` par-dessus.
"""

from __future__ import annotations

import datetime as dt

from comptes import Compte, Comptes
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ContactEleve, ProfilEleve


def calculer_age(date_naissance: dt.date | None, aujourdhui: dt.date | None = None) -> int | None:
    """Âge calculé, jamais stocké (voir §6.4 : "*(Âge)* — Calculé")."""
    if date_naissance is None:
        return None
    aujourdhui = aujourdhui or dt.date.today()
    age = aujourdhui.year - date_naissance.year
    if (aujourdhui.month, aujourdhui.day) < (date_naissance.month, date_naissance.day):
        age -= 1
    return age


class Eleves:
    def __init__(self, comptes: Comptes) -> None:
        self.comptes = comptes

    def list(self, db: Session, ecole_id: int) -> list[Compte]:
        return self.comptes.list_par_role(db, ecole_id, role="eleve")

    def get_compte(self, db: Session, eleve_id: int) -> Compte | None:
        compte = self.comptes.get(db, eleve_id)
        if compte is None or compte.role != "eleve":
            return None
        return compte

    def get_profil(self, db: Session, eleve_id: int) -> ProfilEleve | None:
        return db.get(ProfilEleve, eleve_id)

    def create(
        self,
        db: Session,
        ecole_id: int,
        nom: str,
        prenom: str,
        email: str | None = None,
        telephone: str | None = None,
        date_naissance: dt.date | None = None,
        **profil_champs,
    ) -> tuple[Compte, ProfilEleve]:
        compte = self.comptes.create(
            db,
            ecole_id=ecole_id,
            role="eleve",
            nom=nom,
            prenom=prenom,
            email=email,
            telephone=telephone,
        )
        profil = ProfilEleve(compte_id=compte.id, date_naissance=date_naissance, **profil_champs)
        db.add(profil)
        db.commit()
        db.refresh(profil)
        return compte, profil

    def delete(self, db: Session, eleve_id: int) -> bool:
        """Supprime le profil + les contacts avant le compte lui-même
        (voir comptes.py : le socle commun ne connaît pas ProfilEleve)."""
        compte = self.get_compte(db, eleve_id)
        if compte is None:
            return False
        for contact in self.contacts_de_leleve(db, eleve_id):
            db.delete(contact)
        profil = self.get_profil(db, eleve_id)
        if profil is not None:
            db.delete(profil)
        db.commit()
        return self.comptes.delete(db, eleve_id)

    def update_profil(self, db: Session, eleve_id: int, **champs) -> ProfilEleve | None:
        profil = self.get_profil(db, eleve_id)
        if profil is None:
            return None
        for cle, valeur in champs.items():
            if valeur is not None:
                setattr(profil, cle, valeur)
        db.commit()
        db.refresh(profil)
        return profil

    # --- Contacts (voir §6.4 : plusieurs contacts possibles par élève) ---

    def contacts_de_leleve(self, db: Session, eleve_id: int) -> list[ContactEleve]:
        return list(
            db.scalars(select(ContactEleve).where(ContactEleve.eleve_id == eleve_id))
        )

    def ajouter_contact(self, db: Session, eleve_id: int, **champs) -> ContactEleve:
        contact = ContactEleve(eleve_id=eleve_id, **champs)
        db.add(contact)
        db.commit()
        db.refresh(contact)
        return contact

    def modifier_contact(self, db: Session, contact_id: int, **champs) -> ContactEleve | None:
        contact = db.get(ContactEleve, contact_id)
        if contact is None:
            return None
        for cle, valeur in champs.items():
            if valeur is not None:
                setattr(contact, cle, valeur)
        db.commit()
        db.refresh(contact)
        return contact

    def supprimer_contact(self, db: Session, contact_id: int) -> bool:
        contact = db.get(ContactEleve, contact_id)
        if contact is None:
            return False
        db.delete(contact)
        db.commit()
        return True
