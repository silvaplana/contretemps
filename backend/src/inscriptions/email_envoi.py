"""Envoi des emails d'inscription — à la famille (dossier + facture en
pièces jointes) ET, séparément, à l'administrateur (voir
inscriptions.py:_notifier_admin) — stdlib uniquement (`smtplib`,
`email.mime.*`), même philosophie de désactivation silencieuse que
`notifications/notifications.py` : sans SMTP configuré (voir
.env.example), `actif` == False, `envoyer_confirmation()` ne fait rien de
cassé — un échec d'envoi ne doit JAMAIS faire échouer une inscription
(voir inscriptions.py : chaque étape après l'insertion en base est dans
son propre try/except). `envoyer_confirmation()` reste générique
(destinataire/sujet/corps/pièces jointes) : utilisée telle quelle pour
les deux emails, jamais spécifique à la famille malgré son nom.
"""

from __future__ import annotations

import logging
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


class EmailEnvoi:
    def __init__(self) -> None:
        self.hote = os.environ.get("SMTP_HOST")
        self.port = int(os.environ.get("SMTP_PORT", "587"))
        self.utilisateur = os.environ.get("SMTP_USER")
        self.mot_de_passe = os.environ.get("SMTP_PASSWORD")
        self.nom_expediteur = os.environ.get("SMTP_FROM_NAME", "Contretemps")
        self.actif = bool(self.hote and self.utilisateur and self.mot_de_passe)
        # Destinataire du 2e email (notification admin, voir
        # inscriptions.py:_notifier_admin) — distinct de l'expéditeur
        # (self.utilisateur) pour rester configurable séparément plus
        # tard (ex. si SMTP_USER devient une boîte technique) ; par
        # défaut, part vers la même adresse que l'expéditeur (décision
        # utilisateur : ça marche tout de suite sans rien configurer de
        # plus).
        self.adresse_admin = os.environ.get("ADMIN_EMAIL") or self.utilisateur

    def envoyer_confirmation(
        self,
        destinataire: str,
        sujet: str,
        corps: str,
        pieces_jointes: list[tuple[str, bytes]],
    ) -> None:
        """`pieces_jointes` : liste de (nom_fichier, contenu_bytes).
        Lève une exception en cas d'échec (voir inscriptions.py qui
        l'attrape et journalise `email_erreur` sur la ligne, jamais
        renvoyée en erreur HTTP à la famille qui vient de s'inscrire)."""
        if not self.actif:
            return

        message = MIMEMultipart()
        message["From"] = f"{self.nom_expediteur} <{self.utilisateur}>"
        message["To"] = destinataire
        message["Subject"] = sujet
        message.attach(MIMEText(corps, "plain"))

        for nom_fichier, contenu in pieces_jointes:
            piece = MIMEApplication(contenu, Name=nom_fichier)
            piece["Content-Disposition"] = f'attachment; filename="{nom_fichier}"'
            message.attach(piece)

        with smtplib.SMTP(self.hote, self.port) as serveur:
            serveur.starttls()
            serveur.login(self.utilisateur, self.mot_de_passe)
            serveur.sendmail(self.utilisateur, destinataire, message.as_string())
