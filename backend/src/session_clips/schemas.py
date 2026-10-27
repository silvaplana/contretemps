"""Formes des requêtes et réponses HTTP (Pydantic), pas les tables (voir
models.py)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel

from videos.schemas import VideoSortie


class SessionCreate(BaseModel):
    """« Envoyer la vidéo d'une séance » : l'envoi (`upload_id`, module
    Vidéos) devient la vidéo brute d'une séance."""

    upload_id: str
    title: str = ""
    held_on: date


class FightCreate(BaseModel):
    """« Filmer un combat » : l'envoi (`upload_id`, module Vidéos) et les
    deux combattants, Rouge puis Bleu."""

    upload_id: str
    people: list[int]


class FavoriteUpdate(BaseModel):
    favorite: bool


class ParticipantsUpdate(BaseModel):
    """Les personnes du clip, dans l'ordre des places (Rouge puis Bleu à
    deux) ; `null` : pas encore nommé."""

    people: list[int | None]


class MeOut(BaseModel):
    person_id: int
    is_coach: bool


class PersonOut(BaseModel):
    id: int
    name: str


class ParticipantOut(BaseModel):
    person_id: int | None
    name: str | None


class ClipOut(BaseModel):
    id: int
    session_id: int
    position: int
    title: str
    to_check: bool
    # Dans les « ★ Favoris » de l'appelant.
    favorite: bool = False
    check_reason: str | None = None
    participants: list[ParticipantOut]
    video: VideoSortie | None
    # Pour « Mes combats » et la lecture : la séance en clair.
    session_title: str
    held_on: date


class SessionOut(BaseModel):
    id: int
    title: str
    # Filmée par la caméra de la salle (découpe au fil du cours).
    live: bool = False
    held_on: date
    # 'uploading' (la vidéo arrive), 'processing' (découpe à venir), 'ready'.
    status: str
    clip_count: int
    to_check_count: int
    # Les trois premiers combats, pour l'aperçu de la carte.
    previews: list[VideoSortie]
    # La vidéo brute, suivie par le téléphone qui l'envoie (progression).
    raw_video: VideoSortie | None = None


class SessionDetail(SessionOut):
    clips: list[ClipOut]
    attendees: list[PersonOut]


# --- Caméra de la salle (étape 3) ---


class CameraOut(BaseModel):
    """La pastille et le panneau de la caméra (§6.3). `state` : 'none' (pas
    encore installée), 'ready', 'recording' ou 'offline'."""

    paired: bool
    state: str
    battery_percent: int | None = None
    free_bytes: int | None = None
    pending_pieces: int = 0
    last_upload_at: datetime | None = None
    session_id: int | None = None
    session_title: str = ""
    started_at: datetime | None = None
    signal: str
    pairing_code: str | None = None
    pairing_expires_at: datetime | None = None


class CameraStart(BaseModel):
    title: str = ""


class SignalUpdate(BaseModel):
    signal: str


class RecorderPair(BaseModel):
    code: str


class RecorderPaired(BaseModel):
    token: str


class RecorderHeartbeat(BaseModel):
    state: str  # 'ready' | 'recording'
    battery_percent: int | None = None
    free_bytes: int | None = None
    pending_pieces: int = 0


class RecorderOrders(BaseModel):
    """Ce que le téléphone doit faire : filmer la séance `session_id`
    (vide = rester prêt), avec ce signal « compris »."""

    session_id: int | None
    signal: str


class PieceOpen(BaseModel):
    session_id: int
    position: int
    size: int
    last: bool = False


class PieceOut(BaseModel):
    upload_id: str
    received: int
