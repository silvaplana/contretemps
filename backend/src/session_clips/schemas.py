"""Formes des requêtes et réponses HTTP (Pydantic), pas les tables (voir
models.py)."""

from __future__ import annotations

from datetime import date

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
    check_reason: str | None = None
    participants: list[ParticipantOut]
    video: VideoSortie | None
    # Pour « Mes combats » et la lecture : la séance en clair.
    session_title: str
    held_on: date


class SessionOut(BaseModel):
    id: int
    title: str
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
