"""Détourage par IA sur notre serveur (`rembg`, spec §5.1.1) : aucun
service extérieur, donc gratuit à l'usage. Le paquet est lourd (modèle
d'environ 170 Mo, téléchargé à la première utilisation) : s'il n'est pas
installé, le choix « Par IA » n'est simplement pas proposé."""

from __future__ import annotations

from collections.abc import Callable

from PIL import Image


def detourage_ia_disponible() -> Callable[[Image.Image], Image.Image] | None:
    try:
        from rembg import new_session, remove
    except ImportError:
        return None
    session = {}

    def detourer(image: Image.Image) -> Image.Image:
        if "modele" not in session:
            session["modele"] = new_session("u2net")
        return remove(image, session=session["modele"]).convert("RGBA")

    return detourer
