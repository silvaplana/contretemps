"""Invitations et suivi de l'accès (voir spec/SPEC.md §2.2 : « Invitation »
et « Suivi de l'invitation »). Un seul mail par adresse, même si elle porte
plusieurs profils dans l'école.
"""

from __future__ import annotations

import smtplib

from acces import INVITATION, Acces, AccesEmail, normaliser_email
from acces.acces import FINALISE, INSTALLEE
from comptes import Compte
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import destinataire
from .mails import MailsAcces, MailsIndisponibles


def raison_echec(erreur: Exception) -> str:
    """Raison lisible d'un envoi refusé. Seul un refus IMMÉDIAT du serveur
    de mail est connu ici ; une boîte qui n'existe pas n'est en général
    signalée que plus tard, par un retour de non-remise."""
    if isinstance(erreur, smtplib.SMTPRecipientsRefused):
        return "Adresse refusée par le serveur de mail"
    if isinstance(erreur, smtplib.SMTPAuthenticationError):
        return "Envoi refusé : identifiants du serveur de mail incorrects"
    return "Le mail n'a pas pu être envoyé"


class Invitations:
    def __init__(self, acces: Acces, mails: MailsAcces) -> None:
        self.acces = acces
        self.mails = mails

    def emails_a_inviter(self, db: Session, ecole_id: int, compte_ids: list[int]) -> list[str]:
        """Adresses distinctes des fiches demandées (celles de cette école,
        saison affichée ; les fiches sans email sont ignorées)."""
        fiches = db.scalars(select(Compte).where(Compte.ecole_id == ecole_id, Compte.id.in_(compte_ids)))
        return sorted({normaliser_email(f.email) for f in fiches} - {None})

    def inviter(self, db: Session, ecole, email: str) -> None:
        """Envoie le mail (nouveau lien, qui annule le précédent), puis note
        « Invité le… ». Lève une exception si le mail ne part pas."""
        profils = db.scalars(
            select(Compte).where(Compte.ecole_id == ecole.id, Compte.email.isnot(None)).order_by(Compte.id)
        )
        profils = [p for p in profils if normaliser_email(p.email) == email]
        prenoms = [p.prenom for p in profils]
        a_qui = destinataire(profils)
        acces_email = self.acces.obtenir_ou_creer(db, email)
        nom = f"{a_qui.prenom} {a_qui.nom}"
        try:
            if acces_email.mot_de_passe_hache:
                # Accès déjà créé : un rappel pour se connecter, sans lien
                # pour choisir un mot de passe.
                self.mails.rappel(email, ecole.nom, nom, prenoms)
            else:
                jeton = self.acces.creer_lien(db, acces_email, INVITATION, ecole.id)
                self.mails.invitation(email, ecole.nom, nom, prenoms, jeton)
        except MailsIndisponibles:
            raise  # réglage du serveur, pas un problème de cette adresse
        except Exception as erreur:
            # L'échec se lit ensuite dans la colonne Statut (demande
            # utilisateur du 2026-10-02).
            self.acces.noter_echec_envoi(db, acces_email, raison_echec(erreur))
            raise
        self.acces.noter_invite(db, acces_email)

    def noter_adresse_invalide(self, db: Session, email: str) -> None:
        self.acces.noter_echec_envoi(db, self.acces.obtenir_ou_creer(db, email), "Adresse email mal saisie")

    def statuts(self, db: Session, ecole_id: int) -> dict[int, dict]:
        """{compte_id: {"statut", "date"}} pour toutes les fiches de
        l'école (saison affichée). Le statut appartient à l'email : les
        profils d'une famille affichent le même."""
        fiches = list(db.scalars(select(Compte).where(Compte.ecole_id == ecole_id)))
        emails = {normaliser_email(f.email) for f in fiches} - {None}
        acces_emails = (
            {u.email: u for u in db.scalars(select(AccesEmail).where(AccesEmail.email.in_(emails)))}
            if emails
            else {}
        )
        par_email: dict[str, list[Compte]] = {}
        for fiche in fiches:
            if normaliser_email(fiche.email):
                par_email.setdefault(normaliser_email(fiche.email), []).append(fiche)
        resultat = {}
        for fiche in fiches:
            email = normaliser_email(fiche.email)
            statut, date, detail = self.acces.statut(fiche.email, acces_emails.get(email))
            # « Profil finalisé par <prénom> » : le profil de cette adresse à
            # qui les mails s'adressent (voir auth.py : destinataire).
            par = destinataire(par_email[email]).prenom if statut in (FINALISE, INSTALLEE) else None
            resultat[fiche.id] = {"statut": statut, "date": date, "detail": detail, "par": par}
        return resultat
