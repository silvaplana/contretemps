"""Invitations et suivi de l'accès (voir spec/SPEC.md §2.2 : « Invitation »
et « Suivi de l'invitation »). Un seul mail par adresse, même si elle porte
plusieurs profils dans l'école.
"""

from __future__ import annotations

import smtplib

from acces import INVITATION, Acces, AccesEmail, normaliser_email
from acces.acces import FINALISE, INSTALLEE
from comptes import Compte, EmailCompte
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

    def emails_a_inviter(
        self, db: Session, ecole_id: int, compte_ids: list[int], email: str | None = None
    ) -> list[str]:
        """Adresses distinctes des fiches demandées (celles de cette école,
        saison affichée ; les fiches sans email sont ignorées). Toutes les
        adresses de chaque fiche (§2.1), ou seulement `email` s'il est
        donné (bouton « Inviter » d'une adresse dans la fiche)."""
        fiches = db.scalars(select(Compte).where(Compte.ecole_id == ecole_id, Compte.id.in_(compte_ids)))
        emails = {e for f in fiches for e in f.emails}
        if email is not None:
            emails &= {normaliser_email(email)}
        return sorted(emails)

    def inviter(self, db: Session, ecole, email: str, compte_ids: list[int] | None = None) -> None:
        """Envoie le mail (nouveau lien, qui annule le précédent), puis note
        « Invité le… ». Lève une exception si le mail ne part pas.
        `compte_ids` : les fiches sur lesquelles l'admin a cliqué ; le mail
        salue l'une d'elles, pas un autre profil qui partage l'adresse (vécu
        le 2026-10-15 : « Inviter » sur un élève saluait la professeure qui
        avait la même adresse, de plus haut rang)."""
        profils = list(
            db.scalars(
                select(Compte)
                .where(Compte.ecole_id == ecole.id, Compte.adresses.any(EmailCompte.email == email))
                .order_by(Compte.id)
            )
        )
        prenoms = [p.prenom for p in profils]
        demandes = [p for p in profils if compte_ids and p.id in compte_ids]
        a_qui = destinataire(demandes or profils)
        acces_email = self.acces.obtenir_ou_creer(db, email)
        nouvelle_ecole = acces_email.id not in self.acces.adresses_connues_de(db, ecole.id)
        self.acces.noter_ecole(db, acces_email, ecole.id)
        nom = f"{a_qui.prenom} {a_qui.nom}"
        try:
            if acces_email.mot_de_passe_hache:
                # Accès déjà créé : un rappel pour se connecter, sans lien
                # pour choisir un mot de passe. Première fois pour cette
                # école : « votre mot de passe habituel », sans nommer
                # l'autre école (vécu le 2026-11-12, Sambo).
                self.mails.rappel(
                    email, ecole.nom, nom, prenoms, sous_domaine=ecole.sous_domaine, nouvelle_ecole=nouvelle_ecole
                )
            else:
                jeton = self.acces.creer_lien(db, acces_email, INVITATION, ecole.id)
                self.mails.invitation(email, ecole.nom, nom, prenoms, jeton, sous_domaine=ecole.sous_domaine)
        except MailsIndisponibles:
            raise  # réglage du serveur, pas un problème de cette adresse
        except Exception as erreur:
            # L'échec se lit ensuite dans la colonne Statut (demande
            # utilisateur du 2026-10-02).
            self.acces.noter_echec_envoi(db, acces_email, raison_echec(erreur))
            raise
        self.acces.noter_invite(db, acces_email)

    def noter_adresse_invalide(self, db: Session, ecole_id: int, email: str) -> None:
        acces_email = self.acces.obtenir_ou_creer(db, email)
        self.acces.noter_ecole(db, acces_email, ecole_id)
        self.acces.noter_echec_envoi(db, acces_email, "Adresse email mal saisie")

    def statuts(self, db: Session, ecole_id: int) -> dict[int, dict]:
        """{compte_id: {"statut", "date"}} pour toutes les fiches de
        l'école (saison affichée), seulement pour les adresses que cette
        école connaît (acces.AccessOrg). Le statut appartient à l'email : les
        profils qui partagent une adresse affichent le même pour elle. Une
        fiche à plusieurs emails (§2.1) a une ligne par adresse dans
        `adresses` ; le statut principal est celui de sa première adresse."""
        fiches = list(db.scalars(select(Compte).where(Compte.ecole_id == ecole_id)))
        emails = {e for f in fiches for e in f.emails}
        acces_emails = (
            {u.email: u for u in db.scalars(select(AccesEmail).where(AccesEmail.email.in_(emails)))}
            if emails
            else {}
        )
        # Une adresse connue d'une autre école seulement : « pas invitée »
        # ici (étanchéité, Seb 12/11/2026).
        connues = self.acces.adresses_connues_de(db, ecole_id)
        acces_emails = {e: a for e, a in acces_emails.items() if a.id in connues}
        par_email: dict[str, list[Compte]] = {}
        for fiche in fiches:
            for email in fiche.emails:
                par_email.setdefault(email, []).append(fiche)

        def ligne(email: str | None) -> dict:
            statut, date, detail = self.acces.statut(email, acces_emails.get(email))
            # « Profil finalisé par <prénom> » : le profil de cette adresse à
            # qui les mails s'adressent (voir auth.py : destinataire).
            par = destinataire(par_email[email]).prenom if statut in (FINALISE, INSTALLEE) else None
            return {"email": email, "statut": statut, "date": date, "detail": detail, "par": par}

        resultat = {}
        for fiche in fiches:
            adresses = [ligne(e) for e in fiche.emails]
            principal = dict(adresses[0]) if adresses else ligne(None)
            principal["adresses"] = adresses if len(adresses) > 1 else []
            resultat[fiche.id] = principal
        return resultat
