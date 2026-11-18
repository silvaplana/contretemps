"""Parler à la boîte : IMAP (lecture) et SMTP (envoi) avec un mot de passe
d'application, comme Sambo Admin (backend/src/webmail/). Pas d'OAuth : la
lecture de Gmail par OAuth demande un audit de sécurité annuel payant.
Fournisseurs : Gmail et Infomaniak (Seb, 18 novembre ; spec/modules/mail.md §4)."""

from __future__ import annotations

import imaplib
import smtplib
import ssl
from dataclasses import dataclass

IMAP_PORT, SMTP_PORT = 993, 587  # TLS direct ; STARTTLS (les deux fournisseurs)
TIMEOUT = 20

REFUSED = "Google n'a pas accepté ce code. Vérifiez qu'il est copié en entier, ou créez-en un nouveau."


@dataclass(frozen=True)
class Provider:
    name: str
    imap_host: str
    smtp_host: str
    refused: str


PROVIDERS = {
    "gmail": Provider("Gmail", "imap.gmail.com", "smtp.gmail.com", REFUSED),
    "infomaniak": Provider(
        "Infomaniak",
        "mail.infomaniak.com",
        "mail.infomaniak.com",
        "Infomaniak n'a pas accepté ce mot de passe. Vérifiez qu'il est copié en entier, ou créez-en un nouveau.",
    ),
}


class MailError(Exception):
    """Message lisible par la personne (affiché tel quel)."""


class MailRefused(MailError):
    """Le fournisseur refuse l'adresse ou le mot de passe d'application."""


def check(address: str, password: str, provider: str = "gmail") -> None:
    """Se connecte en IMAP puis en SMTP, sans rien lire ni envoyer."""
    p = PROVIDERS[provider]
    try:
        with imaplib.IMAP4_SSL(p.imap_host, IMAP_PORT, timeout=TIMEOUT) as imap:
            imap.login(address, password)
        with smtplib.SMTP(p.smtp_host, SMTP_PORT, timeout=TIMEOUT) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(address, password)
    except (imaplib.IMAP4.error, smtplib.SMTPAuthenticationError):
        raise MailRefused(p.refused) from None
    except (OSError, smtplib.SMTPException):
        raise MailError(f"{p.name} ne répond pas. Réessayez dans un moment.") from None
