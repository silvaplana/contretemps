"""Déclaration du module Vidéos (spec/core.md §9 bis)."""

from registry import Module

from .receiver import VideosReceiver
from .stockage import DOSSIER_VIDEOS_LIVE
from .videos import Videos


def mount(app, core) -> None:
    # Module générique (voir videos/models.py) : aucune dépendance métier.
    core.videos_client = Videos()
    VideosReceiver(client=core.videos_client, app=app)
    # Les fichiers vidéo (un dossier par école, voir videos/stockage.py) ne
    # sont plus servis en statique : seulement par /videos/{id}/fichier, avec
    # un lien signé à durée limitée (voir securite/liens.py).
    DOSSIER_VIDEOS_LIVE.mkdir(parents=True, exist_ok=True)


MODULE = Module(key="videos", label="Vidéos", mount=mount)
