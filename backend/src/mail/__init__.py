"""Sous-module Mail de la Messagerie (spec/modules/mail.md) : la boîte Gmail
de l'école, lue et envoyée depuis Messages › Mail. Étape 1 : la connexion
(adresse et mot de passe d'application Google, chiffré en base)."""

from .models import MailAccount

__all__ = ["MailAccount"]
