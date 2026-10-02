"""Mots de passe, liens d'invitation et de réinitialisation, suivi de
l'invitation (voir spec/SPEC.md §2.2 et §6.3ter). Ne connaît pas les
comptes : il ne manipule que des adresses email.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from securite import mots_de_passe
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import INVITATION, REINITIALISATION, LienInvitationReinit, AccesEmail, maintenant

LONGUEUR_MIN = 8  # au moins 8 caractères, sans autre règle (§2.2)
DUREES = {INVITATION: timedelta(days=15), REINITIALISATION: timedelta(hours=1)}

# Statuts du suivi de l'invitation (§2.2), dans l'ordre des étapes.
PAS_EMAIL = "pas_email"
PAS_INVITE = "pas_invite"
INVITE = "invite"
CONSULTEE = "consultee"
FINALISE = "finalise"
INSTALLEE = "installee"
ECHEC_ENVOI = "echec_envoi"
REMIS = "remis"


class ErreurAcces(ValueError):
    """Demande refusée : message lisible, renvoyé tel quel à l'écran."""


def normaliser_email(email: str | None) -> str | None:
    email = (email or "").strip().lower()
    return email or None


def _hacher_jeton(jeton: str) -> str:
    return hashlib.sha256(jeton.encode("utf-8")).hexdigest()


def _jour(date: datetime) -> str:
    """« 02/10 », à l'heure de Paris (les dates sont stockées en UTC)."""
    return date.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Europe/Paris")).strftime("%d/%m")


class Acces:
    # --- Utilisateurs (une ligne par email) ---

    def par_email(self, db: Session, email: str | None) -> AccesEmail | None:
        email = normaliser_email(email)
        if email is None:
            return None
        return db.scalar(select(AccesEmail).where(AccesEmail.email == email))

    def obtenir_ou_creer(self, db: Session, email: str) -> AccesEmail:
        acces_email = self.par_email(db, email)
        if acces_email is None:
            acces_email = AccesEmail(email=normaliser_email(email))
            db.add(acces_email)
            db.flush()
        return acces_email

    # --- Mot de passe ---

    def mot_de_passe_valide(self, acces_email: AccesEmail | None, mot_de_passe: str) -> bool:
        return acces_email is not None and mots_de_passe.verifier(mot_de_passe, acces_email.mot_de_passe_hache)

    def definir_mot_de_passe(self, db: Session, acces_email: AccesEmail, mot_de_passe: str) -> None:
        if len(mot_de_passe or "") < LONGUEUR_MIN:
            raise ErreurAcces(f"Le mot de passe doit faire au moins {LONGUEUR_MIN} caractères")
        acces_email.mot_de_passe_hache = mots_de_passe.hacher(mot_de_passe)
        if acces_email.profil_finalise_le is None:
            acces_email.profil_finalise_le = maintenant()
        db.commit()

    def empreinte(self, acces_email: AccesEmail) -> str:
        """Courte empreinte du mot de passe actuel, portée par les jetons de
        session (securite/jetons.py) : changer de mot de passe la change,
        ce qui déconnecte tous les appareils (décision du 2026-10-01)."""
        return hashlib.sha256((acces_email.mot_de_passe_hache or "").encode("utf-8")).hexdigest()[:16]

    # --- Liens d'invitation et de réinitialisation ---

    def creer_lien(self, db: Session, acces_email: AccesEmail, type_: str, ecole_id: int | None = None) -> str:
        """Le jeton EN CLAIR, à mettre dans le lien du mail : il n'est
        stocké nulle part. Annule les liens précédents du même type."""
        db.execute(delete(LienInvitationReinit).where(LienInvitationReinit.acces_email_id == acces_email.id, LienInvitationReinit.type == type_))
        jeton = secrets.token_urlsafe(32)
        db.add(
            LienInvitationReinit(
                acces_email_id=acces_email.id,
                type=type_,
                jeton_hache=_hacher_jeton(jeton),
                expire_le=maintenant() + DUREES[type_],
                ecole_id=ecole_id,
            )
        )
        db.commit()
        return jeton

    def lire_lien(self, db: Session, jeton: str) -> LienInvitationReinit | None:
        """Le lien s'il existe, n'a jamais servi et n'a pas expiré."""
        lien = db.scalar(select(LienInvitationReinit).where(LienInvitationReinit.jeton_hache == _hacher_jeton(jeton or "")))
        if lien is None or lien.utilise_le is not None or lien.expire_le <= maintenant():
            return None
        return lien

    def consommer_lien(self, db: Session, lien: LienInvitationReinit) -> None:
        lien.utilise_le = maintenant()
        db.commit()

    # --- Suivi de l'invitation (§2.2) : le premier signal fixe la date ---

    def noter_invite(self, db: Session, acces_email: AccesEmail) -> None:
        acces_email.invite_le = maintenant()  # dernière invitation envoyée
        acces_email.echec_envoi_le = acces_email.echec_envoi_raison = None
        acces_email.mail_remis_le = None  # celui-ci n'est pas encore remis
        db.commit()

    def noter_mail_remis(self, db: Session, acces_email: AccesEmail) -> None:
        acces_email.mail_remis_le = maintenant()
        acces_email.echec_envoi_le = acces_email.echec_envoi_raison = None
        db.commit()

    def noter_echec_envoi(self, db: Session, acces_email: AccesEmail, raison: str) -> None:
        acces_email.echec_envoi_le = maintenant()
        acces_email.echec_envoi_raison = raison[:255]
        db.commit()

    def noter_consultee(self, db: Session, acces_email: AccesEmail) -> None:
        if acces_email.invitation_consultee_le is None:
            acces_email.invitation_consultee_le = maintenant()
            db.commit()

    def noter_appli_installee(self, db: Session, acces_email: AccesEmail) -> None:
        if acces_email.appli_installee_le is None:
            acces_email.appli_installee_le = maintenant()
            db.commit()

    def statut(self, email: str | None, acces_email: AccesEmail | None) -> tuple[str, datetime | None, str | None]:
        """Dernière étape atteinte et sa date, pour un compte dont l'email
        est `email` (voir le tableau du §2.2)."""
        if normaliser_email(email) is None:
            return PAS_EMAIL, None, None
        if acces_email is None:
            return PAS_INVITE, None, None
        # Un échec d'envoi passe devant « invité » et « consultée », mais
        # pas devant un accès déjà créé (la personne n'a plus besoin du mail).
        for code, date, detail in (
            (INSTALLEE, acces_email.appli_installee_le, None),
            (FINALISE, acces_email.profil_finalise_le, None),
            (ECHEC_ENVOI, acces_email.echec_envoi_le, acces_email.echec_envoi_raison),
            (CONSULTEE, acces_email.invitation_consultee_le, None),
            # Seulement pour une personne invitée : un autre mail remis
            # (mot de passe oublié...) ne vaut pas invitation.
            (REMIS, acces_email.mail_remis_le if acces_email.invite_le else None, None),
            (INVITE, acces_email.invite_le, None),
        ):
            if date is not None:
                if code in (INSTALLEE, FINALISE):
                    detail = self._dernier_mail(acces_email, date)
                return code, date, detail
        return PAS_INVITE, None, None

    def _dernier_mail(self, acces_email: AccesEmail, depuis: datetime) -> str | None:
        """Personne qui a déjà son accès et qu'on a réinvitée ensuite : le
        statut principal reste « Profil finalisé », mais on dit ce qu'est
        devenu ce dernier mail (demande utilisateur du 2026-10-02)."""
        echec, invite = acces_email.echec_envoi_le, acces_email.invite_le
        if echec is not None and echec > depuis:
            return f"Réinvitation du {_jour(echec)} : {acces_email.echec_envoi_raison or 'échec'}"
        if invite is not None and invite > depuis:
            suite = "mail remis" if acces_email.mail_remis_le else "mail envoyé"
            return f"Réinvité le {_jour(invite)} : {suite}"
        return None
