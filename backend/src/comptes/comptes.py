"""Logique métier commune aux comptes (voir spec/SPEC.md §2.1, §6.2, §6.3).

Réutilisée par eleves/profs (création/liste filtrée par rôle) et par auth
(vérification identifiant/code) — comptes ne connaît lui-même ni l'un ni
l'autre, c'est le socle sur lequel ils s'appuient.
"""

from __future__ import annotations

from sqlalchemy import func, select
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
        # Insensible à la casse (voir connecter, §2.2 : le champ "Nom
        # Prénom ou Email" du login doit l'être) — func.lower() plutôt que
        # collation SQLite, portable si un jour on passe à Postgres.
        return db.scalar(
            select(Compte).where(
                Compte.ecole_id == ecole_id, func.lower(Compte.email) == email.lower()
            )
        )

    def trouver_par_nom_prenom(
        self, db: Session, ecole_id: int, nom: str, prenom: str, role: str | None = None
    ) -> list[Compte]:
        """Utilisé par auth (connexion par nom+prénom, voir §2.2 —
        insensible à la casse) et par l'import Excel (détection de
        doublon, voir §6.4bis)."""
        requete = select(Compte).where(
            Compte.ecole_id == ecole_id,
            func.lower(Compte.nom) == nom.lower(),
            func.lower(Compte.prenom) == prenom.lower(),
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
        code_recuperation: str | None = None,
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
            code_recuperation=code_recuperation,
        )
        db.add(compte)
        db.commit()
        db.refresh(compte)
        return compte

    def update(self, db: Session, compte_id: int, **champs) -> Compte | None:
        """Champs communs (nom/prénom/email/téléphone) — utilisé par
        eleves/profs pour éditer leur part de `Compte` (les champs
        spécifiques au rôle sont gérés dans leur propre module), et par
        Profil admin (crayon email/téléphone/code_recuperation)."""
        compte = self.get(db, compte_id)
        if compte is None:
            return None
        # Le regroupement familial (§6.2) se fait par email partagé, PAS
        # figé à la création (get_or_create_famille) — sans ça, changer
        # l'email d'un compte laissait `famille_id` périmé : plus
        # regroupé avec la bonne famille (ou toujours avec l'ancienne).
        # Calculé AVANT le setattr ci-dessous : la recherche d'un compte
        # existant avec ce nouvel email doit se faire sur l'email ACTUEL
        # (pas encore changé) de `compte`, sinon il se retrouverait à se
        # matcher lui-même.
        if "email" in champs and champs["email"] != compte.email:
            compte.famille_id = self.get_or_create_famille(db, compte.ecole_id, champs["email"]).id
        # `champs` ne contient déjà que les champs explicitement fournis
        # (exclude_unset=True côté receiver) — un `if valeur is not None`
        # ici empêchait à tort de vider un champ nullable (ex. effacer
        # l'email/téléphone d'un compte).
        for cle, valeur in champs.items():
            setattr(compte, cle, valeur)
        db.commit()
        db.refresh(compte)
        return compte

    def delete(self, db: Session, compte_id: int) -> bool:
        """Suppression du socle commun — les modules eleves/profs
        suppriment d'abord leurs propres tables (ProfilEleve, contacts...)
        avant d'appeler ceci (voir eleves.py)."""
        compte = self.get(db, compte_id)
        if compte is None:
            return False
        db.delete(compte)
        db.commit()
        return True

    def membres_de_la_famille(self, db: Session, compte_id: int) -> list[Compte]:
        """Pour l'écran Profil et le sélecteur de profil famille (§2.1,
        §4) : les autres comptes de la même famille, lui compris."""
        compte = self.get(db, compte_id)
        if compte is None:
            return []
        return list(
            db.scalars(select(Compte).where(Compte.famille_id == compte.famille_id))
        )
