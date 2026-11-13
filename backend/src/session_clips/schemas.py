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
    # Début du combat dans la vidéo de la séance (la frise).
    start_seconds: float | None = None


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
    # Caméra de la salle (Seb, 12/11) : début du film, durée déjà lue, et où
    # en est la découpe (morceaux lus sur morceaux arrivés ou en cours d'envoi).
    # La petite vignette de la carte : la vidéo du début de la séance.
    cover: VideoSortie | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    filmed_seconds: float = 0
    pieces_read: int = 0
    pieces_total: int = 0
    # L'envoi en cours de la vidéo de la caméra (octets reçus / attendus des
    # morceaux pas encore complets), et si le téléphone caméra répond (Seb, 13/11).
    sent_bytes: int = 0
    size_bytes: int = 0
    camera_online: bool = False


class SessionDetail(SessionOut):
    clips: list[ClipOut]
    attendees: list[PersonOut]
    signs: list[LabSignOut] = []


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
    # La petite vignette de la carte : la vidéo du début de la séance.
    cover: VideoSortie | None = None
    started_at: datetime | None = None
    signal: str
    pairing_code: str | None = None
    pairing_expires_at: datetime | None = None


class ThisPhone(BaseModel):
    """Le jeton remis à l'appli Tournage qui devient la caméra."""

    token: str


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


# --- Labo (§6.5 bis) ---


class LabTestCreate(BaseModel):
    upload_id: str
    title: str = ""


class SessionRename(BaseModel):
    title: str


class LabTestRename(BaseModel):
    title: str


class LabSignOut(BaseModel):
    kind: str
    start: float
    end: float
    thumb: str | None = None


class LabFightOut(BaseModel):
    start: float
    end: float
    fighters: int
    check_reason: str | None = None
    # Le cadre (framing.py) : [t depuis le début, x, y, largeur, hauteur],
    # de 0 à 1 ; vide en plan large.
    frame: list[list[float]] | None = None


class LabTestOut(BaseModel):
    id: int
    title: str
    # 'uploading' (la vidéo arrive), 'processing' (lecture à venir), 'ready', 'failed'.
    status: str
    created_at: datetime
    video: VideoSortie | None


class LabTestDetail(LabTestOut):
    signs: list[LabSignOut]
    fights: list[LabFightOut]


class ClubSignsBody(BaseModel):
    """Réglages de la découpe du club : « Signes et sons du club » cochés
    (voir fights.SIGNS), cadrage (`wide`, `medium`, `tight`) et secondes
    retirées au début et à la fin de chaque combat."""

    signs: list[str]
    framing: str = "wide"
    start_skip: float = 0.0
    end_skip: float = 0.0
    show_timeline: bool = True
