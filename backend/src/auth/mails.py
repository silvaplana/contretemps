"""Mails de l'accès par mot de passe (voir spec/SPEC.md §2.2) : invitation
et réinitialisation. Envoyés par le SMTP déjà utilisé pour les inscriptions
(inscriptions/email_envoi.py) : Brevo le remplacera en changeant seulement
les variables d'environnement `SMTP_*`.

`URL_APPLI` : adresse publique de l'appli, sans barre finale (par défaut
celle de la production). Les liens y mènent ; sur Android, ils ouvrent
directement l'appli si elle est installée (App Links).
"""

from __future__ import annotations

import logging
import os

from inscriptions.email_envoi import EmailEnvoi

logger = logging.getLogger(__name__)


class MailsIndisponibles(RuntimeError):
    """Aucun SMTP configuré sur ce serveur : rien ne peut partir."""


class MailsAcces:
    def __init__(self, envoi: EmailEnvoi | None = None) -> None:
        self.envoi = envoi or EmailEnvoi()
        self.url_appli = os.environ.get("URL_APPLI", "https://silvaplana.cloud/contretemps").rstrip("/")
        # Développement sans SMTP : le mail est écrit dans les journaux du
        # serveur au lieu d'être envoyé (jamais en production).
        self.dans_les_journaux = os.environ.get("MAILS_DANS_LES_JOURNAUX") == "1"

    @property
    def disponible(self) -> bool:
        """Un mail peut-il partir de ce serveur ?"""
        return self.envoi.actif or self.dans_les_journaux

    def lien(self, page: str, jeton: str) -> str:
        return f"{self.url_appli}/{page}?jeton={jeton}"

    def invitation(self, email: str, ecole_nom: str, prenoms: list[str], jeton: str) -> None:
        profils = f"Profils : {', '.join(prenoms)}.\n\n" if len(prenoms) > 1 else ""
        self._envoyer(
            email,
            f"{ecole_nom} vous invite sur son application",
            f"Bonjour,\n\n"
            f"L'école {ecole_nom} vous invite sur son application.\n\n"
            f"{profils}"
            f"Créez votre mot de passe en ouvrant ce lien :\n{self.lien('activer', jeton)}\n\n"
            f"Ce lien est valable 7 jours et ne peut servir qu'une fois.\n",
        )

    def reinitialisation(self, email: str, jeton: str) -> None:
        self._envoyer(
            email,
            "Votre nouveau mot de passe",
            f"Bonjour,\n\n"
            f"Pour choisir un nouveau mot de passe, ouvrez ce lien :\n{self.lien('reinitialiser', jeton)}\n\n"
            f"Ce lien est valable 1 heure et ne peut servir qu'une fois.\n"
            f"Si vous n'avez rien demandé, ignorez ce message : votre mot de passe ne change pas.\n",
        )

    def _envoyer(self, destinataire: str, sujet: str, corps: str) -> None:
        if self.envoi.actif:
            self.envoi.envoyer_confirmation(destinataire, sujet, corps, [])
        elif self.dans_les_journaux:
            logger.warning("Mail non envoyé (pas de SMTP) à %s : %s\n%s", destinataire, sujet, corps)
        else:
            raise MailsIndisponibles("L'envoi de mails n'est pas configuré sur ce serveur")
