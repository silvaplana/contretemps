"""Tables du module session_clips (spec/modules/video-combats.md §6.7).

Module générique : il ne connaît ni la danse ni le combat. Comme une
chorégraphie, il référence ses vidéos dans le module `videos`, jamais
l'inverse. Les personnes sont des `person_id` de l'appli hôte (pour
Contretemps, le premier compte de la chaîne des saisons), sans clé
étrangère : le module ne connaît pas les fiches.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ClipSession(Base):
    """Une séance filmée. `raw_video_id` : la vidéo de toute la séance,
    effacée une fois découpée et validée (étape 2)."""

    __tablename__ = "sc_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # Le cours, en clair (« Adultes · 19 h ») : la séance reste lisible même
    # si le cours change ou disparaît.
    title: Mapped[str] = mapped_column(String(150), nullable=False, default="")
    held_on: Mapped[date] = mapped_column(Date, nullable=False)
    raw_video_id: Mapped[int | None] = mapped_column(ForeignKey("videos.id"), nullable=True)
    # 'processing' : en attente de découpe ; 'ready' : clips prêts ;
    # 'failed' : vidéo illisible (voir app/sparring_worker.py).
    # L'envoi en cours se lit sur la vidéo brute (statut 'en_cours').
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="processing")
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Clip(Base):
    __tablename__ = "sc_clips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sc_sessions.id"), nullable=False, index=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), nullable=False, unique=True)
    # Combat 1, 2… dans la séance.
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    # L'appli n'est pas sûre des noms : le clip attend un coach (§6.4) et
    # n'apparaît dans « Mes combats » qu'une fois validé.
    to_check: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    check_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class ClipParticipant(Base):
    """Qui est dans un clip, de 1 à n. À deux, la place 0 est Rouge (à
    gauche au début du combat) et la place 1 Bleu. `person_id` vide : pas
    encore nommé."""

    __tablename__ = "sc_participants"

    clip_id: Mapped[int] = mapped_column(ForeignKey("sc_clips.id"), primary_key=True)
    slot: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)


class SessionAttendee(Base):
    """Présents reconnus à la séance (passés sur le repère au sol) : la
    liste proposée pour corriger un nom."""

    __tablename__ = "sc_attendees"

    session_id: Mapped[int] = mapped_column(ForeignKey("sc_sessions.id"), primary_key=True)
    person_id: Mapped[int] = mapped_column(Integer, primary_key=True)


class Favorite(Base):
    """« ★ Favoris » : les combats qu'une personne a mis de côté. Propres à
    chacun (un élève ne voit que ses combats, Seb 27/10)."""

    __tablename__ = "sc_favorites"

    person_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clip_id: Mapped[int] = mapped_column(ForeignKey("sc_clips.id"), primary_key=True, index=True)
