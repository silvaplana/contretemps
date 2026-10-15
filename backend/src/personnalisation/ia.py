"""Détourage par IA sur notre serveur (`rembg`, spec §5.1.1) : aucun
service extérieur, donc gratuit à l'usage. Le paquet est lourd (modèle
d'environ 170 Mo, téléchargé à la première utilisation) : s'il n'est pas
installé, le choix « Par IA » n'est simplement pas proposé.

Chargé seulement au premier détourage, jamais au démarrage : son import
seul occupe le processeur de longues secondes (constaté en production le
2026-10-15 : l'API ne répondait plus pendant ce temps)."""

from __future__ import annotations

import importlib.util
from collections.abc import Callable

from PIL import Image


def detourage_ia_disponible() -> Callable[[Image.Image], Image.Image] | None:
    if importlib.util.find_spec("rembg") is None:
        return None
    session = {}

    def detourer(image: Image.Image) -> Image.Image:
        from rembg import new_session, remove

        if "modele" not in session:
            session["modele"] = new_session("u2net")
        return remove(image, session=session["modele"]).convert("RGBA")

    return detourer
