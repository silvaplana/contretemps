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
    # Les autres cours qui dansent la chorégraphie, en plus de celui de l'URL.
    autres_cours_ids: list[int] = []


class ChoregraphieModification(BaseModel):
    nom: str | None = None
    horaire_repetition: str | None = None
    costume: str | None = None
    # Fourni : remplace la liste des cours, le premier en tête. Il faut
    # pouvoir gérer chaque cours ajouté ou retiré.
    cours_ids: list[int] | None = None
    # Fourni : remplace la liste des élèves participants.
    eleve_ids: list[int] | None = None


class ChoregraphieSortie(BaseModel):
    """Une chorégraphie complète : ses élèves et ses vidéos, dans l'ordre."""

    id: int
    # Le premier cours ; `cours_ids` : tous ses cours, celui-ci en tête.
    cours_id: int
    cours_ids: list[int] = []
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
    # Le téléphone a compressé la vidéo avant l'envoi : le serveur ne la
    # recompresse pas (une seule compression, Seb 2026-10-15).
    deja_compresse: bool = False


class ReordonnerVideos(BaseModel):
    ordre_video_ids: list[int]
