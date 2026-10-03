"""Formes des requêtes/réponses HTTP (Pydantic) — pas les tables (voir
models.py).
"""

from datetime import datetime

from pydantic import BaseModel


class VideoModification(BaseModel):
    nom: str | None = None
    description: str | None = None


class VideoSortie(BaseModel):
    id: int
    ecole_id: int
    nom: str
    description: str | None = None
    lien_fichier: str
    poster: str | None = None
    date_publication: datetime
    uploaded_by: int
    duree_secondes: int | None = None
    # 'en_cours' : le fichier n'est pas encore complet (voir
    # videos.py:Televersement) — lien_fichier/poster/duree_secondes pas
    # encore connus. 'complete' sinon (valeur par défaut, y compris pour
    # les vidéos créées sans upload par blocs, ex. démo/import).
    statut: str = "complete"

    model_config = {"from_attributes": True}


# --- Upload par blocs (voir videos.py : Televersement, creer_televersement/
# ecrire_bloc/finaliser) ---


class TeleversementCreation(BaseModel):
    extension: str
    octets_total: int


class TeleversementSortie(BaseModel):
    id: str
    octets_recus: int
    octets_total: int
    complet: bool

    model_config = {"from_attributes": True}


class FinaliserVideoEntree(BaseModel):
    """Clic « Ajouter » : l'envoi (`upload_id`) devient une vidéo. Celui qui
    l'ajoute est l'appelant, jamais une valeur du corps."""

    upload_id: str
    nom: str
    description: str | None = None


class VideoUsage(BaseModel):
    """Une ligne du top 10 (voir VideosReceiver.usage) — taille lue sur le
    disque à la demande, pas stockée (voir Video.duree_secondes pour la
    durée, elle stockée)."""

    id: int
    titre: str
    taille_octets: int
    duree_secondes: int | None = None


class UsageVideosEcole(BaseModel):
    """Réponse du panneau "Usage vidéo" (Admin > École)."""

    # Saison affichée (spec §2.6).
    total_octets: int
    total_secondes: int
    # Toutes les saisons de l'école.
    total_toutes_saisons_octets: int
    total_toutes_saisons_secondes: int
    top_videos: list[VideoUsage]
