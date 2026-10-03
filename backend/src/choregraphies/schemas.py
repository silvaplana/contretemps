"""Formes des requêtes/réponses HTTP (Pydantic) — pas les tables (voir
models.py).
"""

from pydantic import BaseModel
from videos.schemas import VideoSortie


class ChoregraphieCreation(BaseModel):
    nom: str
    horaire_repetition: str | None = None
    costume: str | None = None
    eleve_ids: list[int] = []


class ChoregraphieModification(BaseModel):
    nom: str | None = None
    horaire_repetition: str | None = None
    costume: str | None = None
    # Changer de cours : il faut pouvoir gérer l'ancien ET le nouveau.
    cours_id: int | None = None
    # Fourni : remplace la liste des élèves participants.
    eleve_ids: list[int] | None = None


class ChoregraphieSortie(BaseModel):
    """Une chorégraphie complète : ses élèves et ses vidéos, dans l'ordre."""

    id: int
    cours_id: int
    nom: str
    horaire_repetition: str | None = None
    costume: str | None = None
    eleve_ids: list[int] = []
    videos: list[VideoSortie] = []


class VideoAjout(BaseModel):
    """Clic « Ajouter » : l'envoi (`upload_id`, voir videos/receiver.py)
    devient une vidéo de la chorégraphie."""

    upload_id: str
    nom: str
    description: str | None = None


class ReordonnerVideos(BaseModel):
    ordre_video_ids: list[int]
