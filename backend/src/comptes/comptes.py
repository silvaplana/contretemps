"""Logique métier commune aux comptes (voir spec/SPEC.md §2.1, §6.2, §6.3).

Réutilisée par eleves/profs (création/liste filtrée par rôle) et par auth
(vérification identifiant/code) — comptes ne connaît lui-même ni l'un ni
l'autre, c'est le socle sur lequel ils s'appuient.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Compte, Famille


class Comptes:
    def get(self, db: Session, compte_id: int) -> Compte | None:
        return db.get(Compte, compte_id)

    def list_par_role(self, db: Session, ecole_id: int, role: str) -> list[Compte]:
        return list(
            db.scalars(
                select(Compte).where(Compte.ecole_id == ecole_id, Compte.role == role)
            )
        )

    def trouver_par_email(self, db: Session, ecole_id: int, email: str) -> Compte | None:
        return db.scalar(
            select(Compte).where(Compte.ecole_id == ecole_id, Compte.email == email)
        )

    def trouver_par_nom_prenom(
        self, db: Session, ecole_id: int, nom: str, prenom: str, role: str | None = None
    ) -> list[Compte]:
        """Utilisé par auth (connexion par nom+prénom, voir §2.2) et par
        l'import Excel (détection de doublon, voir §6.4bis)."""
        requete = select(Compte).where(
            Compte.ecole_id == ecole_id, Compte.nom == nom, Compte.prenom == prenom
        )
        if role is not None:
            requete = requete.where(Compte.role == role)
        return list(db.scalars(requete))

    def get_or_create_famille(self, db: Session, ecole_id: int, email: str | None) -> Famille:
        """Regroupement automatique par email, DANS une même école (voir
        §6.2). Un compte sans email reste seul dans sa propre famille."""
        if email:
            existant = db.scalar(
                select(Compte).where(Compte.ecole_id == ecole_id, Compte.email == email)
            )
            if existant is not None:
                return existant.famille
        famille = Famille(ecole_id=ecole_id)
        db.add(famille)
        db.flush()
        return famille

    def create(
        self,
        db: Session,
        ecole_id: int,
        role: str,
        nom: str,
        prenom: str,
        email: str | None = None,
        telephone: str | None = None,
    ) -> Compte:
        famille = self.get_or_create_famille(db, ecole_id, email)
        compte = Compte(
            ecole_id=ecole_id,
            famille_id=famille.id,
            role=role,
            nom=nom,
            prenom=prenom,
            email=email,
            telephone=telephone,
        )
        db.add(compte)
        db.commit()
        db.refresh(compte)
        return compte

    def membres_de_la_famille(self, db: Session, compte_id: int) -> list[Compte]:
        """Pour l'écran Profil et le sélecteur de profil famille (§2.1,
        §4) : les autres comptes de la même famille, lui compris."""
        compte = self.get(db, compte_id)
        if compte is None:
            return []
        return list(
            db.scalars(select(Compte).where(Compte.famille_id == compte.famille_id))
        )
