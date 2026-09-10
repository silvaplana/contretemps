"""Formes des requêtes/réponses HTTP (Pydantic) — pas les tables (voir
models.py).
"""

from datetime import datetime

from pydantic import BaseModel


class VideoCreation(BaseModel):
    nom: str
    lien_fichier: str
    uploaded_by: int
    choregraphie_id: int | None = None
    description: str | None = None
    ordre: int | None = None
    poster: str | None = None
    duree_secondes: int | None = None


class VideoModification(BaseModel):
    nom: str | None = None
    lien_fichier: str | None = None
    choregraphie_id: int | None = None
    description: str | None = None
    ordre: int | None = None
    poster: str | None = None
    duree_secondes: int | None = None


class VideoSortie(BaseModel):
    id: int
    cours_id: int
    choregraphie_id: int | None = None
    nom: str
    description: str | None = None
    lien_fichier: str
    poster: str | None = None
    date_publication: datetime
    uploaded_by: int
    ordre: int | None = None
    duree_secondes: int | None = None

    model_config = {"from_attributes": True}


class ReordonnerVideos(BaseModel):
    ordre_video_ids: list[int]


class VideoUsage(BaseModel):
    """Une ligne du top 10 (voir VideosReceiver.usage) — taille lue sur le
    disque à la demande, pas stockée (voir Video.duree_secondes pour la
    durée, elle stockée)."""

    id: int
    titre: str
    cours: str
    choregraphie: str | None = None
    taille_octets: int
    duree_secondes: int | None = None


class UsageVideosEcole(BaseModel):
    """Réponse du panneau "Usage vidéo" (Admin > École)."""

    total_octets: int
    total_secondes: int
    top_videos: list[VideoUsage]
