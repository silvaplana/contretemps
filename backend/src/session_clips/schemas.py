"""Formes des requêtes et réponses HTTP (Pydantic), pas les tables (voir
models.py)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from videos.schemas import VideoSortie


class SessionCreate(BaseModel):
    """« Envoyer la vidéo d'une séance » : l'envoi (`upload_id`, module
    Vidéos) devient la vidéo brute d'une séance."""

    upload_id: str
    title: str = ""
    held_on: date


class OverlayPhase(BaseModel):
    """Un round (`n` ≥ 1) ou un repos (`n` = 0) qui commence à `t` secondes
    dans la vidéo, pour `total` secondes."""

    t: float
    n: int
    total: int


class OverlayRequest(BaseModel):
    """Timer étendu : ce qu'il faut incruster dans la vidéo archivée (cases
    de Paramètres du Timer, musique choisie à « Archiver »)."""

    names: bool = False
    winner: bool = False
    chrono: bool = False
    music: Literal["montage", "entree", "rock"] | None = None
    announce: bool = False  # George annonce le vainqueur, après le gong
    rounds: int = 1
    phases: list[OverlayPhase] = []


class FightCreate(BaseModel):
    """« Filmer un combat » : l'envoi (`upload_id`, module Vidéos) et les
    deux combattants, sans ordre ; le Timer étendu peut laisser un nom
    vide et donner le résultat."""

    upload_id: str
    people: list[int | None]
    # Timer étendu : la place (0 ou 1) du vainqueur, vide si personne n'est déclaré.
    winner: int | None = None
    draw: bool = False  # match nul
    overlay: OverlayRequest | None = None


class FavoriteUpdate(BaseModel):
    favorite: bool


class ParticipantsUpdate(BaseModel):
    """Les personnes du clip, dans l'ordre des places ; `null` : pas encore
    nommé ; `"outsider"` : quelqu'un qui n'est pas du club (Seb, 17/11)."""

    people: list[int | Literal["outsider"] | None]


class PersonName(BaseModel):
    """Qui est la personne repérée (Qui est qui ?, Seb 17/11) : un membre,
    `"outsider"` (pas du club) ou `null` (retirer le nom)."""

    who: int | Literal["outsider"] | None


class Proposal(BaseModel):
    member_id: int
    name: str
    reason: str


class FoundPerson(BaseModel):
    n: int
    image: str | None
    label: str
    member_id: int | None
    outsider: bool
    name: str | None
    fights: int
    proposal: Proposal | None


class PeopleOut(BaseModel):
    ready: bool
    persons: list[FoundPerson]
    filled: int  # combats dont toutes les places sont nommées
    total: int


class MeOut(BaseModel):
    person_id: int
    is_coach: bool


class PersonOut(BaseModel):
    id: int
    name: str
    regular: bool = False  # Timer étendu : habitué de ce jour de la semaine


class ParticipantOut(BaseModel):
    person_id: int | None
    name: str | None
    outsider: bool = False
    winner: bool = False


class ClipOut(BaseModel):
    id: int
    session_id: int
    position: int
    title: str
    to_check: bool
    draw: bool = False  # match nul déclaré au Timer étendu
    # Le serveur incruste encore la vidéo (Seb, 21/11 : « qu'on le sache »).
    preparing: bool = False
    # Dans les « ★ Favoris » de l'appelant.
    favorite: bool = False
    check_reason: str | None = None
    participants: list[ParticipantOut]
    new: bool = False  # un combat validé de celui qui regarde, pas encore ouvert
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


class FilmPart(BaseModel):
    """Un bout du film de la séance et où il commence dans la séance."""

    start: float
    video: VideoSortie


class SessionDetail(SessionOut):
    clips: list[ClipOut]
    attendees: list[PersonOut]
    signs: list[LabSignOut] = []
    # Le film entier, à voir même sans combat trouvé (Seb, 13/11).
    film: list[FilmPart] = []


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
    # Ce que voit la caméra, une image toutes les 4 s (Seb, 13/11).
    image: str | None = None
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
    # Un cri : son volume (dB au-dessus du bruit de fond) et sa note de 0 à 1 (Seb, 14/11).
    db: float | None = None
    note: float | None = None


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
    loud_only: bool = False
    sure_only: bool = False
    loud_db: float = 6.0
    sure_min: float = 0.5
    speech_model: str = "base"
    min_hold: float = 1.6  # durée minimale d'un geste tenu, en secondes


class VoiceAnswer(BaseModel):
    """Bon, Mauvais ou Inventé sous un mot trouvé par « Tester » (Seb, 14/11)."""

    t: float
    answer: str  # good | wrong | invented
    word: str | None = None  # le mot trouvé (good) ou le mot dit (wrong ; « other » : un autre mot)


class VoiceNote(BaseModel):
    """Un cri noté dans une séance filmée (étude du 14/11) : Bon, Mauvais,
    Inventé, ou « missing » (Il manque un mot, au moment de la vidéo)."""

    t: float
    answer: str  # good | wrong | invented | missing
    word: str | None = None


class GestureNote(BaseModel):
    """Un geste noté dans la frise d'une séance (Seb, 15/11) : Bon, Mauvais
    (`real` : le vrai geste, s'il y en avait un), Inventé, ou « missing »
    (Il manque un geste ici)."""

    t: float
    kind: str  # fists_touch | arms_up | handshake | x
    answer: str  # good | wrong | invented | missing
    real: str | None = None


class VoiceMissing(BaseModel):
    """« Il manque un mot » après un test (Seb, 14/11)."""

    word: str
