"""Le service email du core pour les modules : un mail au nom de l'école
(spec/modules/helloasso.md §7.6 : « l'envoi passe par le service email du
core, avec réponse vers l'adresse de l'école »). Rangé dans `core.mail_ecole`
(app/main.py) ; même SMTP que les inscriptions et les mails d'accès."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
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


def envoyer_a_chacun(
    db: Session,
    ecole_id: int,
    adresses: list[str],
    contenu: Callable[[str], tuple[str, str, str]],
    repondre_a: str | None = None,
    images: list[tuple[str, bytes]] | None = None,
) -> list[str]:
    """Un mail par adresse, au nom de l'école (personne ne voit les autres) :
    pour écrire aux adhérents (Publications, Mail ; Seb, 19 novembre 2026).
    `contenu(adresse)` rend (sujet, texte, html), propre à chacun (lien de
    désinscription). Les réponses vont à `repondre_a`, sinon à l'email de
    contact de l'école, jamais à l'expéditeur de l'enseigne (Brevo, qui ne
    reçoit rien). Une adresse refusée n'arrête pas les autres. Rend les
    adresses servies ; lève une exception si l'envoi n'est pas configuré, ou
    si aucune adresse n'est servie (avec la raison du dernier refus)."""
    from personnalisation import brands

    ecole = db.get(Ecole, ecole_id)
    reponse = repondre_a or (ecole.email_contact or "").strip() or None
    if not _envoi.actif:
        if os.environ.get("MAILS_DANS_LES_JOURNAUX") == "1":
            logger.warning("Mails non envoyés (pas de SMTP) à %s adresses", len(adresses))
            return list(adresses)
        raise RuntimeError("L’envoi de mails n’est pas configuré sur ce serveur")
    expediteur = (ecole.nom, brands.of_nature(ecole.nature).sender_email)
    servies, refus = [], None
    for adresse in adresses:
        sujet, texte, html = contenu(adresse)
        try:
            _envoi.envoyer_confirmation(
                adresse, sujet, texte, [], html, expediteur=expediteur, images=images, repondre_a=reponse
            )
            servies.append(adresse)
        except Exception as erreur:  # noqa: BLE001 - une adresse refusée n'arrête pas les autres
            logger.exception("Mail non envoyé à une adresse de l'école %s", ecole_id)
            refus = erreur
    if adresses and not servies:
        raise RuntimeError(f"Le mail n’est pas parti : {refus}") from refus
    return servies
