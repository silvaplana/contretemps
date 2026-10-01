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
from html import escape

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

    # Mails rédigés pour ne pas finir en spam (constaté le 2026-10-01 avec
    # Gmail : un titre qui parle de « mot de passe », trois lignes et un lien
    # nu ressemblent à de l'hameçonnage) : titre neutre, texte qui dit qui
    # écrit et pourquoi, version mise en forme en plus de la version texte. « Bonjour Prénom Nom, » : demande utilisateur.
    # `destinataire` : la personne à qui l'on s'adresse quand l'adresse
    # porte plusieurs profils (voir auth.py : destinataire).
    def _sujet(self, ecole_nom: str | None) -> str:
        return f"Votre accès à l'application {ecole_nom or 'Contretemps'}"

    def invitation(self, email: str, ecole_nom: str, destinataire: str, prenoms: list[str], jeton: str) -> None:
        paragraphes = [
            f"L'école {ecole_nom} utilise une application pour ses élèves, leurs familles et ses "
            "professeurs : messages de l'école, vidéos et chorégraphies des cours, présences.",
            "Votre accès est prêt. Pour l'activer, ouvrez le lien ci-dessous et choisissez votre mot de passe. "
            "Vous pourrez ensuite vous connecter avec cette adresse email.",
        ]
        if len(prenoms) > 1:
            paragraphes.append(f"Profils : {', '.join(prenoms)}.")
        self._composer(
            email,
            ecole_nom,
            destinataire,
            paragraphes,
            "Activer mon accès",
            self.lien("activer", jeton),
            [
                "Ce lien est valable 7 jours et ne peut servir qu'une fois.",
                f"Ce message vous est envoyé à la demande de l'école {ecole_nom}. "
                "Si vous ne la connaissez pas, vous pouvez l'ignorer.",
            ],
        )

    def rappel(self, email: str, ecole_nom: str, destinataire: str, prenoms: list[str]) -> None:
        """Réinvitation d'une personne qui a DÉJÀ créé son mot de passe
        (demande utilisateur du 2026-10-02) : pas de lien pour en choisir
        un, juste l'adresse de l'appli et le rappel de « Mot de passe
        oublié ? »."""
        paragraphes = [
            f"L'école {ecole_nom} vous rappelle que votre accès à son application est déjà actif.",
            f"Pour vous connecter, ouvrez l'application et saisissez votre adresse email ({email}) "
            "et votre mot de passe.",
            "Si vous ne vous souvenez plus de votre mot de passe, cliquez sur « Mot de passe oublié ? » "
            "sur l'écran de connexion : vous recevrez un lien pour en choisir un nouveau.",
        ]
        if len(prenoms) > 1:
            paragraphes.append(f"Profils : {', '.join(prenoms)}.")
        self._composer(
            email,
            ecole_nom,
            destinataire,
            paragraphes,
            "Ouvrir l'application",
            f"{self.url_appli}/",
            [
                f"Ce message vous est envoyé à la demande de l'école {ecole_nom}. "
                "Si vous ne la connaissez pas, vous pouvez l'ignorer.",
            ],
        )

    def reinitialisation(self, email: str, ecole_nom: str | None, destinataire: str, jeton: str) -> None:
        nom = ecole_nom or "Contretemps"
        self._composer(
            email,
            ecole_nom,
            destinataire,
            [
                f"Vous avez demandé à choisir un nouveau mot de passe pour l'application {nom}. "
                "Ouvrez le lien ci-dessous pour le définir.",
            ],
            "Choisir mon mot de passe",
            self.lien("reinitialiser", jeton),
            [
                "Ce lien est valable 1 heure et ne peut servir qu'une fois.",
                "Si vous n'avez rien demandé, ignorez ce message : votre mot de passe ne change pas.",
            ],
        )

    def _composer(
        self,
        email: str,
        ecole_nom: str | None,
        destinataire: str,
        paragraphes: list[str],
        bouton: str,
        lien: str,
        fin: list[str],
    ) -> None:
        """Les deux versions du même message, texte et mise en forme, avec le
        lien écrit en clair dans les deux."""
        texte = "\n\n".join([f"Bonjour {destinataire},", *paragraphes, f"{bouton} :\n{lien}", *fin]) + "\n"
        p = '<p style="margin:0 0 16px">{}</p>'
        html = (
            '<div style="font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:1.5;color:#3a2410;'
            'max-width:520px">'
            + p.format(f"Bonjour {escape(destinataire)},")
            + "".join(p.format(escape(x)) for x in paragraphes)
            # Pas de bouton ni de balise de lien : Brevo réécrit tout lien
            # cliquable vers son domaine de suivi, sans réglage pour l'éviter
            # (constaté le 2026-10-02). Une adresse écrite en clair n'est pas
            # réécrite, et les messageries la rendent cliquable.
            + f'<p style="margin:24px 0 4px;font-weight:bold">{escape(bouton)} :</p>'
            + f'<p style="margin:0 0 24px;word-break:break-all">{escape(lien)}</p>'
            + "".join('<p style="margin:0 0 8px;font-size:13px;color:#8a6a4a">{}</p>'.format(escape(x)) for x in fin)
            + "</div>"
        )
        self._envoyer(email, self._sujet(ecole_nom), texte, html)

    def _envoyer(self, destinataire: str, sujet: str, corps: str, corps_html: str | None = None) -> None:
        if self.envoi.actif:
            self.envoi.envoyer_confirmation(destinataire, sujet, corps, [], corps_html)
        elif self.dans_les_journaux:
            logger.warning("Mail non envoyé (pas de SMTP) à %s : %s\n%s", destinataire, sujet, corps)
        else:
            raise MailsIndisponibles("L'envoi de mails n'est pas configuré sur ce serveur")
