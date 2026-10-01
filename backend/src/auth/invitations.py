"""Invitations et suivi de l'accès (voir spec/SPEC.md §2.2 : « Invitation »
et « Suivi de l'invitation »). Un seul mail par adresse, même si elle porte
plusieurs profils dans l'école.
"""

from __future__ import annotations

from acces import INVITATION, Acces, AccesEmail, normaliser_email
from comptes import Compte
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import destinataire
from .mails import MailsAcces


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
        jeton = self.acces.creer_lien(db, acces_email, INVITATION, ecole.id)
        self.mails.invitation(email, ecole.nom, f"{a_qui.prenom} {a_qui.nom}", prenoms, jeton)
        self.acces.noter_invite(db, acces_email)

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
        resultat = {}
        for fiche in fiches:
            statut, date = self.acces.statut(fiche.email, acces_emails.get(normaliser_email(fiche.email)))
            resultat[fiche.id] = {"statut": statut, "date": date}
        return resultat
