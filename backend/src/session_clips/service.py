"""Logique du module session_clips (spec/modules/video-combats.md §6) :
séances filmées, clips, noms des participants, file « À vérifier ».

La découpe elle-même (repérer les poings levés et les X, couper, nommer) est faite par
le worker de l'étape 2, qui range ses clips par `add_clip`.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from saisons.portee import toutes_saisons
from videos import Video, Videos

from . import people
from .models import Clip, ClipParticipant, ClipSession, Favorite, LabTest, Piece, Recorder, SessionAttendee, Viewed
from .overlay import thumbnail_from_frame
from .overlay import wanted as overlay_wanted
from .ports import Directory, Member, Notifier


class NotFoundError(Exception):
    pass


class ForbiddenError(Exception):
    pass


OUTSIDER = "outsider"  # quelqu'un qui n'est pas du club (Seb, 17/11)
OUTSIDER_NAME = "Inconnu"


def _shown_to_fighters(clip: Clip) -> bool:
    """Un combattant nommé voit le combat même si l'autre nom attend un coach
    (Seb, 21/11) ; pas un clip découpé douteux (`check_reason`)."""
    return not clip.to_check or clip.check_reason is None

class SessionClips:
    def __init__(self, videos: Videos, directory: Directory, notifier: Notifier | None = None) -> None:
        self.videos = videos
        self.directory = directory
        self.notifier = notifier
        # Une vidéo supprimée (d'ici ou du panneau « Usage vidéo ») emporte
        # son clip, ou détache la séance de sa vidéo brute.
        videos.quand_supprimee(self._video_deleted)
        videos.rubrique("Fights", self._video_ids)

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

    def outsiders(self, db: Session, clip_ids: list[int]) -> set[tuple[int, int]]:
        """Les places (clip, place) tenues par quelqu'un qui n'est pas du club."""
        if not clip_ids:
            return set()
        rows = db.execute(
            select(ClipParticipant.clip_id, ClipParticipant.slot).where(
                ClipParticipant.clip_id.in_(clip_ids), ClipParticipant.outsider.is_(True)
            )
        )
        return {(c, s) for c, s in rows}

    def winners(self, db: Session, clip_ids: list[int]) -> set[tuple[int, int]]:
        """Les places (clip, place) déclarées vainqueur."""
        if not clip_ids:
            return set()
        rows = db.execute(
            select(ClipParticipant.clip_id, ClipParticipant.slot).where(
                ClipParticipant.clip_id.in_(clip_ids), ClipParticipant.winner.is_(True)
            )
        )
        return {(c, s) for c, s in rows}

    def attendees(self, db: Session, session_id: int) -> list[int]:
        return list(db.scalars(select(SessionAttendee.person_id).where(SessionAttendee.session_id == session_id)))

    def name_order(self, db: Session, session: ClipSession) -> list[int]:
        """Tous les membres pour choisir un nom (Seb, 17/11) : d'abord ceux de
        la séance (présents, déjà nommés), puis ceux qui ont combattu le même
        jour de la semaine les 8 semaines d'avant (les plus fréquents d'abord),
        puis les autres par ordre alphabétique."""
        people = sorted(self.directory.people(db, session.org_id), key=lambda p: p.name.lower())
        known = {p.id for p in people}
        counts = self._same_day_counts(db, session.org_id, session.held_on)
        here = set(self.attendees(db, session.id)) | set(
            db.scalars(
                select(ClipParticipant.person_id)
                .join(Clip, Clip.id == ClipParticipant.clip_id)
                .where(Clip.session_id == session.id, ClipParticipant.person_id.is_not(None))
            )
        )
        rank = {p.id: n for n, p in enumerate(people)}
        first = sorted(here & known, key=rank.get)
        regulars = sorted(set(counts) & known - here, key=lambda i: (-counts[i], rank[i]))
        rest = [p.id for p in people if p.id not in here and p.id not in counts]
        return first + regulars + rest

    def _same_day_counts(self, db: Session, org_id: int, day: date) -> dict[int, int]:
        """Combien de fois chacun a combattu le même jour de la semaine, les 8 semaines avant `day`."""
        since = date.fromordinal(day.toordinal() - 56)
        before = db.execute(
            select(ClipSession.id, ClipSession.held_on).where(
                ClipSession.org_id == org_id,
                ClipSession.held_on >= since,
                ClipSession.held_on < day,
            )
        )
        same_day = [i for i, d in before if d.weekday() == day.weekday()]
        counts: dict[int, int] = {}
        for person_id in db.scalars(
            select(ClipParticipant.person_id)
            .join(Clip, Clip.id == ClipParticipant.clip_id)
            .where(Clip.session_id.in_(same_day), ClipParticipant.person_id.is_not(None))
        ):
            counts[person_id] = counts.get(person_id, 0) + 1
        return counts

    def regulars(self, db: Session, org_id: int, day: date) -> list[int]:
        """Timer étendu (★) : les habitués de ce jour de la semaine, les plus fréquents d'abord."""
        people = sorted(self.directory.people(db, org_id), key=lambda p: p.name.lower())
        rank = {p.id: n for n, p in enumerate(people)}
        counts = self._same_day_counts(db, org_id, day)
        return sorted(set(counts) & set(rank), key=lambda i: (-counts[i], rank[i]))

    def timer_order(self, db: Session, org_id: int, day: date) -> list[int]:
        """Les habitués d'abord, puis les autres par ordre alphabétique."""
        first = self.regulars(db, org_id, day)
        people = sorted(self.directory.people(db, org_id), key=lambda p: p.name.lower())
        return first + [p.id for p in people if p.id not in set(first)]

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
            not _shown_to_fighters(clip) or member.person_id not in self.participants(db, [clip.id])[clip.id]
        ):
            raise NotFoundError("Clip introuvable")
        return clip

    def my_clips(self, db: Session, member: Member) -> list[Clip]:
        """« Mes combats » : les clips où la personne apparaît, du plus récent
        au plus ancien ; aussi ceux où seul l'autre nom manque (Seb, 21/11)."""
        return list(
            db.scalars(
                select(Clip)
                .join(ClipSession, ClipSession.id == Clip.session_id)
                .join(ClipParticipant, ClipParticipant.clip_id == Clip.id)
                .where(
                    ClipSession.org_id == member.org_id,
                    ClipParticipant.person_id == member.person_id,
                    or_(Clip.to_check.is_(False), Clip.check_reason.is_(None)),
                )
                .order_by(ClipSession.held_on.desc(), ClipSession.id.desc(), Clip.position)
            )
        )

    def viewed_ids(self, db: Session, person_id: int, clip_ids: list[int]) -> set[int]:
        if not clip_ids:
            return set()
        return set(db.scalars(select(Viewed.clip_id).where(Viewed.person_id == person_id, Viewed.clip_id.in_(clip_ids))))

    def new_count(self, db: Session, member: Member) -> int:
        """Les combats validés de la personne qu'elle n'a pas encore ouverts."""
        mine = [c.id for c in self.my_clips(db, member)]
        return len(mine) - len(self.viewed_ids(db, member.person_id, mine))

    def set_thumb(self, db: Session, member: Member, clip_id: int, jpeg: bytes, duration: float | None = None) -> None:
        """La première image du combat, prise par le téléphone qui l'a filmé
        (Seb, 22/11) : visible dans Combats avant la fin de l'envoi, avec les
        incrustations demandées (noms, chrono) déjà posées."""
        if not member.is_coach:
            raise ForbiddenError("Réservé aux coachs")
        if not jpeg.startswith(b"\xff\xd8") or len(jpeg) > 1_000_000:
            raise ValueError("Vignette illisible")
        clip = self.clip(db, member, clip_id)
        video = self.videos.get(db, clip.video_id)
        if video is None:
            return
        if overlay_wanted(clip.overlay):
            try:
                jpeg = thumbnail_from_frame(jpeg, clip.overlay, duration)
            except Exception:  # noqa: BLE001 — l'image seule plutôt que rien
                pass
        self.videos.poser_vignette(db, video, jpeg)

    def mark_viewed(self, db: Session, member: Member, clip: Clip) -> None:
        """La personne ouvre un de ses combats validés : il n'est plus nouveau."""
        if not _shown_to_fighters(clip) or member.person_id not in self.participants(db, [clip.id])[clip.id]:
            return
        if db.get(Viewed, (member.person_id, clip.id)) is None:
            db.add(Viewed(person_id=member.person_id, clip_id=clip.id))
            db.commit()

    def to_check(self, db: Session, org_id: int) -> list[Clip]:
        return list(
            db.scalars(
                select(Clip)
                .join(ClipSession, ClipSession.id == Clip.session_id)
                .where(ClipSession.org_id == org_id, Clip.to_check.is_(True))
                .order_by(ClipSession.held_on.desc(), ClipSession.id.desc(), Clip.position)
            )
        )

    def favorites(self, db: Session, member: Member) -> list[Clip]:
        """« ★ Favoris » de l'appelant, du plus récent au plus ancien, parmi
        les clips qu'il peut voir."""
        clips = db.scalars(
            select(Clip)
            .join(Favorite, Favorite.clip_id == Clip.id)
            .join(ClipSession, ClipSession.id == Clip.session_id)
            .where(Favorite.person_id == member.person_id, ClipSession.org_id == member.org_id)
            .order_by(ClipSession.held_on.desc(), ClipSession.id.desc(), Clip.position)
        )
        visible = []
        for clip in clips:
            try:
                visible.append(self.clip(db, member, clip.id))
            except NotFoundError:
                pass
        return visible

    def favorite_ids(self, db: Session, person_id: int, clip_ids: list[int]) -> set[int]:
        if not clip_ids:
            return set()
        return set(
            db.scalars(select(Favorite.clip_id).where(Favorite.person_id == person_id, Favorite.clip_id.in_(clip_ids)))
        )

    # --- Écriture ---

    def set_favorite(self, db: Session, member: Member, clip_id: int, favorite: bool) -> Clip:
        clip = self.clip(db, member, clip_id)
        row = db.get(Favorite, (member.person_id, clip.id))
        if favorite and row is None:
            db.add(Favorite(person_id=member.person_id, clip_id=clip.id))
        elif not favorite and row is not None:
            db.delete(row)
        db.commit()
        return clip

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

    def add_fight(
        self, db: Session, member: Member, upload_id: str, people: list[int | None], winner: int | None = None,
        draw: bool = False, overlay: dict | None = None,
    ) -> Clip:
        """« Filmer un combat » (bouton +) : un combat filmé à la main, gardé,
        puis nommé. Il rejoint la séance du jour, sans vidéo entière ni
        découpe, et part tout de suite dans « Mes combats » des combattants.
        La vidéo est compressée par le worker du module Vidéos.

        Timer étendu (Seb, 21/11) : un nom peut manquer (le combat attend
        alors un coach), `winner` est la place du vainqueur déclaré et `draw`
        un match nul. `overlay` : ce qu'il faut incruster (overlay.py) ; la
        vidéo n'est alors compressée qu'une fois, avec l'incrustation."""
        self._require_coach(member)
        if len(people) != 2 or (people[0] is not None and people[0] == people[1]):
            raise ValueError("Choisissez deux combattants différents")
        if winner not in (None, 0, 1) or (draw and winner is not None):
            raise ValueError("Vainqueur inconnu")
        known = {p.id for p in self.directory.people(db, member.org_id)}
        if any(p is not None and p not in known for p in people):
            raise ValueError("Ce membre n'est pas de l'organisation")
        upload = self.videos.obtenir_televersement(db, upload_id)
        if upload is None or upload.ecole_id != member.org_id:
            raise NotFoundError("Envoi introuvable")
        if upload.video_id is not None:  # double clic : le combat existe déjà
            clip = db.scalar(select(Clip).where(Clip.video_id == upload.video_id))
            if clip is not None:
                return clip
        today = date.today()
        session = db.scalar(
            select(ClipSession).where(
                ClipSession.org_id == member.org_id,
                ClipSession.held_on == today,
                ClipSession.raw_video_id.is_(None),
                ClipSession.status == "ready",
            )
        )
        if session is None:
            session = ClipSession(org_id=member.org_id, held_on=today, status="ready", created_by=member.person_id)
            db.add(session)
            db.flush()
        position = (db.scalar(select(func.max(Clip.position)).where(Clip.session_id == session.id)) or 0) + 1
        incrust = overlay_wanted(overlay)
        video = self.videos.finaliser(
            db, upload_id, nom=video_name(today, "", f"combat {position}"), uploaded_by=member.person_id,
            deja_compresse=incrust,
        )
        clip = self.add_clip(db, session.id, video.id, people)
        if incrust:
            names = {p.id: p.name for p in self.directory.people(db, member.org_id)}
            clip.overlay = {
                **overlay,
                "labels": [names.get(p) if p else None for p in people],
                "people": people,
                "voices": [self.directory.full_name(db, member.org_id, p) if p else None for p in people],
                "result": "draw" if draw else winner,
            }
        if winner is not None:
            db.get(ClipParticipant, (clip.id, winner)).winner = True
        clip.draw = draw
        db.commit()
        if not clip.to_check:
            self._announce(db, member.org_id, clip)
        return clip

    def add_clip(
        self,
        db: Session,
        session_id: int,
        video_id: int,
        people: list[int | None],
        to_check: bool = False,
        check_reason: str | None = None,
        start_seconds: float | None = None,
    ) -> Clip:
        """Range un clip découpé (worker de l'étape 2) à la fin de la séance."""
        last = db.scalar(select(func.max(Clip.position)).where(Clip.session_id == session_id))
        clip = Clip(
            session_id=session_id,
            video_id=video_id,
            position=(last or 0) + 1,
            to_check=to_check or bool(check_reason) or not people or None in people,
            check_reason=check_reason,
            start_seconds=start_seconds,
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

    def set_participants(self, db: Session, member: Member, clip_id: int, people: list[int | str | None]) -> Clip:
        """Nommer ou changer un nom (coachs), `"outsider"` pour quelqu'un qui
        n'est pas du club. Le nombre de places ne change pas."""
        self._require_coach(member)
        clip = self.clip(db, member, clip_id)
        rows = list(
            db.scalars(select(ClipParticipant).where(ClipParticipant.clip_id == clip.id).order_by(ClipParticipant.slot))
        )
        if len(people) != len(rows):
            raise ValueError("Le nombre de combattants ne change pas")
        known = {p.id for p in self.directory.people(db, member.org_id)}
        if any(p not in (None, OUTSIDER) and p not in known for p in people):
            raise ValueError("Ce membre n'est pas de l'organisation")
        for row, person_id in zip(rows, people):
            row.outsider = person_id == OUTSIDER
            row.person_id = None if row.outsider else person_id
        db.commit()
        return clip

    def validate(self, db: Session, member: Member, clip_id: int) -> Clip:
        """« C'est bon » : le clip part dans « Mes combats » de chacun."""
        self._require_coach(member)
        clip = self.clip(db, member, clip_id)
        rows = db.scalars(select(ClipParticipant).where(ClipParticipant.clip_id == clip.id))
        if any(r.person_id is None and not r.outsider for r in rows):
            raise ValueError("Choisissez d'abord tous les noms")
        was_new = clip.to_check
        clip.to_check = False
        clip.check_reason = None
        db.commit()
        if was_new:
            self._announce(db, member.org_id, clip)
        return clip

    def _announce(self, db: Session, org_id: int, clip: Clip) -> None:
        """« Nouveau combat » sur le téléphone de chaque combattant (Seb, 17/11)."""
        people = [p for p in self.participants(db, [clip.id])[clip.id] if p is not None]
        if self.notifier is None or not people:
            return
        names = self.directory.names(db, org_id, set(people))
        outsiders = len(self.outsiders(db, [clip.id]))
        shown = [names.get(p, "?") for p in self.participants(db, [clip.id])[clip.id] if p is not None]
        title = clip_title(shown + [OUTSIDER_NAME] * outsiders)
        self.notifier.notify(db, org_id, people, "Nouveau combat", f"{title} : il est dans Fights › Combats.")

    def delete_clip(self, db: Session, member: Member, clip_id: int) -> None:
        self._require_coach(member)
        clip = self.clip(db, member, clip_id)
        with toutes_saisons(db):
            self.videos.delete(db, clip.video_id)

    def rename_session(self, db: Session, member: Member, session_id: int, title: str) -> ClipSession:
        """Le crayon de la carte (Seb, 12/11)."""
        self._require_coach(member)
        session = self.session(db, member, session_id)
        if not title:
            raise ValueError("Donnez un nom à la séance")
        session.title = title[:150]
        db.commit()
        return session

    def recut_session(self, db: Session, member: Member, session_id: int) -> None:
        """« Relancer la découpe » d'une séance de la caméra finie (Seb, 13/11) :
        elle repasse à la découpe, qui reprend les postures et les sons gardés
        avec les règles du jour. Elle repart de zéro : les anciens combats sont
        effacés (Seb, 14/11)."""
        self._require_coach(member)
        session = self.session(db, member, session_id)
        # Aussi après « Découpe impossible » (Seb, 14/11 : séance 10 bloquée).
        if session.status not in ("ready", "failed") or session.raw_video_id is not None:
            return
        with toutes_saisons(db):
            for video_id in db.scalars(select(Clip.video_id).where(Clip.session_id == session.id)).all():
                self.videos.delete(db, video_id)
        session.status = "processing"
        db.commit()

    def delete_session(self, db: Session, member: Member, session_id: int) -> None:
        """La poubelle de la carte (Seb, 12/11) : la séance, ses combats et sa
        vidéo. Effacée pendant le film, la caméra s'arrête."""
        self._require_coach(member)
        session = self.session(db, member, session_id)
        people.forget(session.org_id, session.id)
        clip_videos = list(db.scalars(select(Clip.video_id).where(Clip.session_id == session.id)))
        piece_videos = list(db.scalars(select(Piece.video_id).where(Piece.session_id == session.id, Piece.video_id.is_not(None))))
        with toutes_saisons(db):
            for video_id in [*clip_videos, *piece_videos, session.raw_video_id]:
                if video_id is not None:
                    self.videos.delete(db, video_id)
        db.execute(delete(Piece).where(Piece.session_id == session.id))
        db.execute(delete(SessionAttendee).where(SessionAttendee.session_id == session.id))
        for recorder in db.scalars(select(Recorder).where(Recorder.session_id == session.id)):
            recorder.session_id = None
            recorder.started_at = None
        db.delete(session)
        db.commit()

    # --- Aides ---

    @staticmethod
    def _require_coach(member: Member) -> None:
        if not member.is_coach:
            raise ForbiddenError("Réservé aux coachs")

    @staticmethod
    def _video_ids(db: Session) -> set[int]:
        """Les vidéos du module : clips, vidéos entières des séances et
        morceaux filmés par la caméra de la salle, vidéos du Labo."""
        return (
            set(db.scalars(select(Clip.video_id)))
            | set(db.scalars(select(ClipSession.raw_video_id).where(ClipSession.raw_video_id.is_not(None))))
            | set(db.scalars(select(Piece.video_id).where(Piece.video_id.is_not(None))))
            | set(db.scalars(select(LabTest.video_id).where(LabTest.video_id.is_not(None))))
        )

    def _video_deleted(self, db: Session, video_id: int) -> None:
        clip_ids = list(db.scalars(select(Clip.id).where(Clip.video_id == video_id)))
        if clip_ids:
            db.execute(delete(ClipParticipant).where(ClipParticipant.clip_id.in_(clip_ids)))
            db.execute(delete(Favorite).where(Favorite.clip_id.in_(clip_ids)))
            # SQLite redonne les numéros libérés : un nouveau combat ne doit
            # pas hériter du « déjà vu » de l'ancien (Seb, 22/11).
            db.execute(delete(Viewed).where(Viewed.clip_id.in_(clip_ids)))
            db.execute(delete(Clip).where(Clip.id.in_(clip_ids)))
        for session in db.scalars(select(ClipSession).where(ClipSession.raw_video_id == video_id)):
            session.raw_video_id = None
        for piece in db.scalars(select(Piece).where(Piece.video_id == video_id)):
            piece.video_id = None
        db.execute(delete(LabTest).where(LabTest.video_id == video_id))


def clip_title(names: list[str | None], repeat: int = 1) -> str:
    """« Seb R. vs Karim B. », suivi de 2, 3… quand la même paire combat
    encore dans la séance (§6.3). « Combat sans nom » quand personne n'est
    nommé."""
    if not names or all(n is None for n in names):
        return "Combat sans nom"
    shown = [n or "?" for n in names]
    if len(shown) == 1:
        title = shown[0]
    elif len(shown) == 2:
        title = f"{shown[0]} vs {shown[1]}"
    else:
        title = f"{', '.join(shown[:-1])} et {shown[-1]}"
    return f"{title} {repeat}" if repeat > 1 else title


def video_name(held_on: date, title: str, what: str) -> str:
    """Nom d'une vidéo de la séance dans le module `videos`, lisible dans
    « Usage des ressources » (Admin > École) : « Fights · 23/10/2026 ·
    Adultes · 19 h · combat 1 »."""
    return " · ".join(part for part in ("Fights", held_on.strftime("%d/%m/%Y"), title, what) if part)
