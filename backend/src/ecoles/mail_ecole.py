"""Le service email du core pour les modules : un mail au nom de l'école
(spec/modules/helloasso.md §7.6 : « l'envoi passe par le service email du
core, avec réponse vers l'adresse de l'école »). Rangé dans `core.mail_ecole`
(app/main.py) ; même SMTP que les inscriptions et les mails d'accès."""

from __future__ import annotations

import logging
import os
from copy import copy

from sqlalchemy.orm import Session

from inscriptions.email_envoi import EmailEnvoi

from .models import Ecole

logger = logging.getLogger(__name__)

_envoi = EmailEnvoi()


def envoyer(db: Session, ecole_id: int, a: str, sujet: str, texte: str, html: str) -> str | None:
    """Envoie, au nom de l'école (expéditeur de son enseigne), avec son email
    de contact en copie et en adresse de réponse. Rend l'adresse en copie ;
    lève une exception si le mail ne part pas."""
    from personnalisation import brands

    ecole = db.get(Ecole, ecole_id)
    contact = (ecole.email_contact or "").strip() or None
    if not _envoi.actif:
        if os.environ.get("MAILS_DANS_LES_JOURNAUX") == "1":
            logger.warning("Mail non envoyé (pas de SMTP) à %s : %s\n%s", a, sujet, texte)
            return contact
        raise RuntimeError("L’envoi de mails n’est pas configuré sur ce serveur")
    envoi = copy(_envoi)
    envoi.repondre_a = contact or _envoi.repondre_a
    envoi.envoyer_confirmation(
        a, sujet, texte, [], html, copie=contact, expediteur=(ecole.nom, brands.of_nature(ecole.nature).sender_email)
    )
    return contact
