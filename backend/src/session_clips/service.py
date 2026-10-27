"""Logique du module session_clips (spec/modules/video-combats.md §6) :
séances filmées, clips, noms des participants, file « À vérifier ».

La découpe elle-même (repérer les poings levés et les X, couper, nommer) est faite par
le worker de l'étape 2, qui range ses clips par `add_clip`.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from saisons.portee import toutes_saisons
from videos import Video, Videos

from .models import Clip, ClipParticipant, ClipSession, SessionAttendee
from .ports import Directory, Member


class NotFoundError(Exception):
    pass


class ForbiddenError(Exception):
    pass


class SessionClips:
    def __init__(self, videos: Videos, directory: Directory) -> None:
        self.videos = videos
        self.directory = directory
        # Une vidéo supprimée (d'ici ou du panneau « Usage vidéo ») emporte
        # son clip, ou détache la séance de sa vidéo brute.
        videos.quand_supprimee(self._video_deleted)
        videos.rubrique("Sparring", self._video_ids)

    # --- Lecture ---

    def sessions(self, db: Session, org_id: int) -> list[ClipSession]:
        return list(
            db.scalars(
                select(ClipSession)
                .where(ClipSession.org_id == org_id)
                .order_by(ClipSession.held_on.desc(), ClipSession.id.desc())
            )
        )

    def session(self, db: Session, member: Member, session_id: int) -> ClipSession:
        session = db.get(ClipSession, session_id)
        if session is None or session.org_id != member.org_id:
            raise NotFoundError("Séance introuvable")
        return session

    def clips_by_session(self, db: Session, session_ids: list[int]) -> dict[int, list[Clip]]:
        result: dict[int, list[Clip]] = {i: [] for i in session_ids}
        if session_ids:
            for clip in db.scalars(
                select(Clip).where(Clip.session_id.in_(session_ids)).order_by(Clip.position, Clip.id)
            ):
                result[clip.session_id].append(clip)
        return result

    def participants(self, db: Session, clip_ids: list[int]) -> dict[int, list[int | None]]:
        """Les personnes de chaque clip, dans l'ordre des places."""
        result: dict[int, list[int | None]] = {i: [] for i in clip_ids}
        if clip_ids:
            for row in db.scalars(
                select(ClipParticipant)
                .where(ClipParticipant.clip_id.in_(clip_ids))
                .order_by(ClipParticipant.slot)
            ):
                result[row.clip_id].append(row.person_id)
        return result

    def attendees(self, db: Session, session_id: int) -> list[int]:
        return list(db.scalars(select(SessionAttendee.person_id).where(SessionAttendee.session_id == session_id)))

    def video_map(self, db: Session, video_ids: list[int]) -> dict[int, Video]:
        # Une séance d'une saison passée garde ses vidéos lisibles.
        with toutes_saisons(db):
            return self.videos.par_ids(db, [i for i in video_ids if i is not None])

    def clip(self, db: Session, member: Member, clip_id: int) -> Clip:
        """Le clip, s'il est de l'organisation et visible par l'appelant :
        un coach voit tout, un membre ses clips validés."""
        clip = db.get(Clip, clip_id)
        if clip is None or db.get(ClipSession, clip.session_id).org_id != member.org_id:
            raise NotFoundError("Clip introuvable")
        if not member.is_coach and (
            clip.to_check or member.person_id not in self.participants(db, [clip.id])[clip.id]
        ):
            raise NotFoundError("Clip introuvable")
        return clip

    def my_clips(self, db: Session, member: Member) -> list[Clip]:
        """« Mes combats » : les clips validés où la personne apparaît, du
        plus récent au plus ancien."""
        return list(
            db.scalars(
                select(Clip)
                .join(ClipSession, ClipSession.id == Clip.session_id)
                .join(ClipParticipant, ClipParticipant.clip_id == Clip.id)
                .where(
                    ClipSession.org_id == member.org_id,
                    ClipParticipant.person_id == member.person_id,
                    Clip.to_check.is_(False),
                )
                .order_by(ClipSession.held_on.desc(), ClipSession.id.desc(), Clip.position)
            )
        )

    def to_check(self, db: Session, org_id: int) -> list[Clip]:
        return list(
            db.scalars(
                select(Clip)
                .join(ClipSession, ClipSession.id == Clip.session_id)
                .where(ClipSession.org_id == org_id, Clip.to_check.is_(True))
                .order_by(ClipSession.held_on.desc(), ClipSession.id.desc(), Clip.position)
            )
        )

    # --- Écriture ---

    def create_session(
        self, db: Session, member: Member, upload_id: str, title: str, held_on: date
    ) -> ClipSession:
        """La vidéo d'une séance, envoyée à la main par le module Vidéos
        (envoi par blocs). Elle n'est pas compressée : elle sera découpée,
        puis effacée."""
        upload = self.videos.obtenir_televersement(db, upload_id)
        if upload is None or upload.ecole_id != member.org_id:
            raise NotFoundError("Envoi introuvable")
        video = self.videos.finaliser(
            db, upload_id, nom=video_name(held_on, title, "vidéo entière"), uploaded_by=member.person_id, deja_compresse=True
        )
        session = db.scalar(select(ClipSession).where(ClipSession.raw_video_id == video.id))
        if session is None:  # sinon, double clic : la séance existe déjà
            session = ClipSession(
                org_id=member.org_id, title=title, held_on=held_on, raw_video_id=video.id, created_by=member.person_id
            )
            db.add(session)
            db.commit()
            db.refresh(session)
        return session

    def add_clip(
        self,
        db: Session,
        session_id: int,
        video_id: int,
        people: list[int | None],
        to_check: bool = False,
        check_reason: str | None = None,
    ) -> Clip:
        """Range un clip découpé (worker de l'étape 2) à la fin de la séance."""
        last = db.scalar(select(func.max(Clip.position)).where(Clip.session_id == session_id))
        clip = Clip(
            session_id=session_id,
            video_id=video_id,
            position=(last or 0) + 1,
            to_check=to_check or bool(check_reason) or not people or None in people,
            check_reason=check_reason,
        )
        db.add(clip)
        db.flush()
        for slot, person_id in enumerate(people):
            db.add(ClipParticipant(clip_id=clip.id, slot=slot, person_id=person_id))
        db.commit()
        db.refresh(clip)
        return clip

    def set_attendees(self, db: Session, session_id: int, person_ids: list[int]) -> None:
        db.execute(delete(SessionAttendee).where(SessionAttendee.session_id == session_id))
        for person_id in dict.fromkeys(person_ids):
            db.add(SessionAttendee(session_id=session_id, person_id=person_id))
        db.commit()

    def set_participants(self, db: Session, member: Member, clip_id: int, people: list[int | None]) -> Clip:
        """Inverser, nommer ou changer un nom (coachs). Le nombre de places
        ne change pas."""
        self._require_coach(member)
        clip = self.clip(db, member, clip_id)
        rows = list(
            db.scalars(select(ClipParticipant).where(ClipParticipant.clip_id == clip.id).order_by(ClipParticipant.slot))
        )
        if len(people) != len(rows):
            raise ValueError("Le nombre de combattants ne change pas")
        known = {p.id for p in self.directory.people(db, member.org_id)}
        if any(p is not None and p not in known for p in people):
            raise ValueError("Ce membre n'est pas de l'organisation")
        for row, person_id in zip(rows, people):
            row.person_id = person_id
        db.commit()
        return clip

    def validate(self, db: Session, member: Member, clip_id: int) -> Clip:
        """« C'est bon » : le clip part dans « Mes combats » de chacun."""
        self._require_coach(member)
        clip = self.clip(db, member, clip_id)
        if None in self.participants(db, [clip.id])[clip.id]:
            raise ValueError("Choisissez d'abord tous les noms")
        clip.to_check = False
        clip.check_reason = None
        db.commit()
        return clip

    def delete_clip(self, db: Session, member: Member, clip_id: int) -> None:
        self._require_coach(member)
        clip = self.clip(db, member, clip_id)
        with toutes_saisons(db):
            self.videos.delete(db, clip.video_id)

    # --- Aides ---

    @staticmethod
    def _require_coach(member: Member) -> None:
        if not member.is_coach:
            raise ForbiddenError("Réservé aux coachs")

    @staticmethod
    def _video_ids(db: Session) -> set[int]:
        """Les vidéos du module : clips et vidéos entières des séances."""
        return set(db.scalars(select(Clip.video_id))) | set(
            db.scalars(select(ClipSession.raw_video_id).where(ClipSession.raw_video_id.is_not(None)))
        )

    def _video_deleted(self, db: Session, video_id: int) -> None:
        clip_ids = list(db.scalars(select(Clip.id).where(Clip.video_id == video_id)))
        if clip_ids:
            db.execute(delete(ClipParticipant).where(ClipParticipant.clip_id.in_(clip_ids)))
            db.execute(delete(Clip).where(Clip.id.in_(clip_ids)))
        for session in db.scalars(select(ClipSession).where(ClipSession.raw_video_id == video_id)):
            session.raw_video_id = None


def clip_title(names: list[str | None], repeat: int = 1) -> str:
    """« Seb R. contre Karim B. », suivi de 2, 3… quand la même paire combat
    encore dans la séance (§6.3). « Combat sans nom » quand personne n'est
    nommé."""
    if not names or all(n is None for n in names):
        return "Combat sans nom"
    shown = [n or "?" for n in names]
    if len(shown) == 1:
        title = shown[0]
    elif len(shown) == 2:
        title = f"{shown[0]} contre {shown[1]}"
    else:
        title = f"{', '.join(shown[:-1])} et {shown[-1]}"
    return f"{title} {repeat}" if repeat > 1 else title


def video_name(held_on: date, title: str, what: str) -> str:
    """Nom d'une vidéo de la séance dans le module `videos`, lisible dans
    « Usage des ressources » (Admin > École) : « Sparring · 23/10/2026 ·
    Adultes · 19 h · combat 1 »."""
    return " · ".join(part for part in ("Sparring", held_on.strftime("%d/%m/%Y"), title, what) if part)
