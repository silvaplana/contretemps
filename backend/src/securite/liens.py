"""Liens signés à durée limitée, pour les fichiers que le navigateur lit
lui-même (balise <video>, image d'aperçu) : il ne sait pas y joindre la
session (en-tête `Authorization`). Le serveur remet donc, à qui a le droit
de voir l'objet, une adresse qui porte sa date d'expiration et une
signature (même secret que les jetons de session, voir jetons.py). Une
adresse copiée ou partagée cesse de marcher à l'expiration.

L'expiration est arrondie à une fenêtre de 6 heures : la même adresse est
remise pendant 6 heures (le navigateur garde la vidéo et l'aperçu en
cache), et reste valable entre 6 et 12 heures.
"""

from __future__ import annotations

import time

from . import jetons

FENETRE_SECONDES = 6 * 3600


def parametres(objet: str, maintenant: float | None = None) -> str:
    """`e=<expiration>&s=<signature>` pour l'objet désigné (ex. "video:12:fichier")."""
    maintenant = time.time() if maintenant is None else maintenant
    expiration = (int(maintenant) // FENETRE_SECONDES + 2) * FENETRE_SECONDES
    return f"e={expiration}&s={jetons.signer(f'lien:{objet}:{expiration}')}"


def valide(objet: str, expiration: str | None, signature: str | None, maintenant: float | None = None) -> bool:
    if not expiration or not signature or not expiration.isdigit():
        return False
    maintenant = time.time() if maintenant is None else maintenant
    if int(expiration) < maintenant:
        return False
    return jetons.signatures_egales(jetons.signer(f"lien:{objet}:{expiration}"), signature)
