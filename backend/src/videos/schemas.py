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


class VideoModification(BaseModel):
    nom: str | None = None
    lien_fichier: str | None = None
    choregraphie_id: int | None = None
    description: str | None = None
    ordre: int | None = None


class VideoSortie(BaseModel):
    id: int
    cours_id: int
    choregraphie_id: int | None = None
    nom: str
    description: str | None = None
    lien_fichier: str
    date_publication: datetime
    uploaded_by: int
    ordre: int | None = None

    model_config = {"from_attributes": True}


class ReordonnerVideos(BaseModel):
    ordre_video_ids: list[int]
