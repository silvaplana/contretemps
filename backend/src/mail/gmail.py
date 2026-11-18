"""Parler à Gmail : IMAP (lecture) et SMTP (envoi) avec un mot de passe
d'application Google, comme Sambo Admin (backend/src/webmail/). Pas d'OAuth :
la lecture de Gmail par OAuth demande un audit de sécurité annuel payant."""

from __future__ import annotations

import imaplib
import smtplib
import ssl

IMAP_HOST, IMAP_PORT = "imap.gmail.com", 993
SMTP_HOST, SMTP_PORT = "smtp.gmail.com", 587
TIMEOUT = 20

REFUSED = "Google n'a pas accepté ce code. Vérifiez qu'il est copié en entier, ou créez-en un nouveau."
UNREACHABLE = "Gmail ne répond pas. Réessayez dans un moment."


class MailError(Exception):
    """Message lisible par la personne (affiché tel quel)."""


class MailRefused(MailError):
    """Google refuse l'adresse ou le mot de passe d'application."""


def check(address: str, password: str) -> None:
    """Se connecte en IMAP puis en SMTP, sans rien lire ni envoyer."""
    try:
        with imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, timeout=TIMEOUT) as imap:
            imap.login(address, password)
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=TIMEOUT) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(address, password)
    except (imaplib.IMAP4.error, smtplib.SMTPAuthenticationError):
        raise MailRefused(REFUSED) from None
    except (OSError, smtplib.SMTPException):
        raise MailError(UNREACHABLE) from None
