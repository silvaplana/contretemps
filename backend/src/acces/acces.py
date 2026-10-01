"""Mots de passe, liens d'invitation et de réinitialisation, suivi de
l'invitation (voir spec/SPEC.md §2.2 et §6.3ter). Ne connaît pas les
comptes : il ne manipule que des adresses email.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta

from securite import mots_de_passe
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import INVITATION, REINITIALISATION, LienAcces, Utilisateur, maintenant

LONGUEUR_MIN = 8  # au moins 8 caractères, sans autre règle (§2.2)
DUREES = {INVITATION: timedelta(days=7), REINITIALISATION: timedelta(hours=1)}

# Statuts du suivi de l'invitation (§2.2), dans l'ordre des étapes.
PAS_EMAIL = "pas_email"
PAS_INVITE = "pas_invite"
INVITE = "invite"
CONSULTEE = "consultee"
FINALISE = "finalise"
INSTALLEE = "installee"


class ErreurAcces(ValueError):
    """Demande refusée : message lisible, renvoyé tel quel à l'écran."""


def normaliser_email(email: str | None) -> str | None:
    email = (email or "").strip().lower()
    return email or None


def _hacher_jeton(jeton: str) -> str:
    return hashlib.sha256(jeton.encode("utf-8")).hexdigest()


class Acces:
    # --- Utilisateurs (une ligne par email) ---

    def par_email(self, db: Session, email: str | None) -> Utilisateur | None:
        email = normaliser_email(email)
        if email is None:
            return None
        return db.scalar(select(Utilisateur).where(Utilisateur.email == email))

    def obtenir_ou_creer(self, db: Session, email: str) -> Utilisateur:
        utilisateur = self.par_email(db, email)
        if utilisateur is None:
            utilisateur = Utilisateur(email=normaliser_email(email))
            db.add(utilisateur)
            db.flush()
        return utilisateur

    # --- Mot de passe ---

    def mot_de_passe_valide(self, utilisateur: Utilisateur | None, mot_de_passe: str) -> bool:
        return utilisateur is not None and mots_de_passe.verifier(mot_de_passe, utilisateur.hashed_password)

    def definir_mot_de_passe(self, db: Session, utilisateur: Utilisateur, mot_de_passe: str) -> None:
        if len(mot_de_passe or "") < LONGUEUR_MIN:
            raise ErreurAcces(f"Le mot de passe doit faire au moins {LONGUEUR_MIN} caractères")
        utilisateur.hashed_password = mots_de_passe.hacher(mot_de_passe)
        if utilisateur.profil_finalise_le is None:
            utilisateur.profil_finalise_le = maintenant()
        db.commit()

    def empreinte(self, utilisateur: Utilisateur) -> str:
        """Courte empreinte du mot de passe actuel, portée par les jetons de
        session (securite/jetons.py) : changer de mot de passe la change,
        ce qui déconnecte tous les appareils (décision du 2026-10-01)."""
        return hashlib.sha256((utilisateur.hashed_password or "").encode("utf-8")).hexdigest()[:16]

    # --- Liens d'invitation et de réinitialisation ---

    def creer_lien(self, db: Session, utilisateur: Utilisateur, type_: str, ecole_id: int | None = None) -> str:
        """Le jeton EN CLAIR, à mettre dans le lien du mail : il n'est
        stocké nulle part. Annule les liens précédents du même type."""
        db.execute(delete(LienAcces).where(LienAcces.utilisateur_id == utilisateur.id, LienAcces.type == type_))
        jeton = secrets.token_urlsafe(32)
        db.add(
            LienAcces(
                utilisateur_id=utilisateur.id,
                type=type_,
                jeton_hache=_hacher_jeton(jeton),
                expire_le=maintenant() + DUREES[type_],
                ecole_id=ecole_id,
            )
        )
        db.commit()
        return jeton

    def lire_lien(self, db: Session, jeton: str) -> LienAcces | None:
        """Le lien s'il existe, n'a jamais servi et n'a pas expiré."""
        lien = db.scalar(select(LienAcces).where(LienAcces.jeton_hache == _hacher_jeton(jeton or "")))
        if lien is None or lien.utilise_le is not None or lien.expire_le <= maintenant():
            return None
        return lien

    def consommer_lien(self, db: Session, lien: LienAcces) -> None:
        lien.utilise_le = maintenant()
        db.commit()

    # --- Suivi de l'invitation (§2.2) : le premier signal fixe la date ---

    def noter_invite(self, db: Session, utilisateur: Utilisateur) -> None:
        utilisateur.invite_le = maintenant()  # dernière invitation envoyée
        db.commit()

    def noter_consultee(self, db: Session, utilisateur: Utilisateur) -> None:
        if utilisateur.invitation_consultee_le is None:
            utilisateur.invitation_consultee_le = maintenant()
            db.commit()

    def noter_appli_installee(self, db: Session, utilisateur: Utilisateur) -> None:
        if utilisateur.appli_installee_le is None:
            utilisateur.appli_installee_le = maintenant()
            db.commit()

    def statut(self, email: str | None, utilisateur: Utilisateur | None) -> tuple[str, datetime | None]:
        """Dernière étape atteinte et sa date, pour un compte dont l'email
        est `email` (voir le tableau du §2.2)."""
        if normaliser_email(email) is None:
            return PAS_EMAIL, None
        if utilisateur is None:
            return PAS_INVITE, None
        for code, date in (
            (INSTALLEE, utilisateur.appli_installee_le),
            (FINALISE, utilisateur.profil_finalise_le),
            (CONSULTEE, utilisateur.invitation_consultee_le),
            (INVITE, utilisateur.invite_le),
        ):
            if date is not None:
                return code, date
        return PAS_INVITE, None
