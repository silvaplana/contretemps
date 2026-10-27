"""Routes REST du module session_clips (/session-clips/...). Qui appelle est
fourni par l'appli hôte (`current_member`, une dépendance FastAPI qui
renvoie un `Member`) ; les droits sont vérifiés par le service."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from db import get_db
from videos.schemas import VideoSortie

from .models import Clip, ClipSession
from .ports import Member
from .schemas import (
    ClipOut,
    FightCreate,
    MeOut,
    ParticipantOut,
    ParticipantsUpdate,
    PersonOut,
    SessionCreate,
    SessionDetail,
    SessionOut,
)
from .service import ForbiddenError, NotFoundError, SessionClips, clip_title

PREFIX = "/session-clips"


class SessionClipsReceiver:
    def __init__(self, client: SessionClips, app: FastAPI, current_member: Callable[..., Member]) -> None:
        self.client = client
        member = Depends(current_member)
        db = Depends(get_db)

        def guard(action):
            try:
                return action()
            except NotFoundError as err:
                raise HTTPException(status_code=404, detail=str(err)) from err
            except ForbiddenError as err:
                raise HTTPException(status_code=403, detail=str(err)) from err
            except ValueError as err:
                raise HTTPException(status_code=400, detail=str(err)) from err

        def coach(m: Member) -> None:
            if not m.is_coach:
                raise HTTPException(status_code=403, detail="Réservé aux coachs")

        @app.get(f"{PREFIX}/me", response_model=MeOut)
        def me(m: Member = member):
            """Qui regarde : sa personne (pour nommer l'adversaire) et s'il est coach."""
            return MeOut(person_id=m.person_id, is_coach=m.is_coach)

        @app.get(f"{PREFIX}/sessions", response_model=list[SessionOut])
        def list_sessions(m: Member = member, s: Session = db):
            coach(m)
            sessions = client.sessions(s, m.org_id)
            return self._sessions_out(s, m, sessions)

        @app.post(f"{PREFIX}/sessions", response_model=SessionOut, status_code=201)
        def create_session(body: SessionCreate, m: Member = member, s: Session = db):
            coach(m)
            session = guard(lambda: client.create_session(s, m, body.upload_id, body.title.strip(), body.held_on))
            return self._sessions_out(s, m, [session])[0]

        @app.post(f"{PREFIX}/fights", response_model=ClipOut, status_code=201)
        def create_fight(body: FightCreate, m: Member = member, s: Session = db):
            return self._clips_out(s, m, [guard(lambda: client.add_fight(s, m, body.upload_id, body.people))])[0]

        @app.get(f"{PREFIX}/sessions/{{session_id}}", response_model=SessionDetail)
        def get_session(session_id: int, m: Member = member, s: Session = db):
            coach(m)
            session = guard(lambda: client.session(s, m, session_id))
            base = self._sessions_out(s, m, [session])[0]
            clips = client.clips_by_session(s, [session.id])[session.id]
            attendees = client.attendees(s, session.id)
            names = client.directory.names(s, m.org_id, set(attendees))
            return SessionDetail(
                **base.model_dump(),
                clips=self._clips_out(s, m, clips),
                attendees=sorted((PersonOut(id=i, name=names.get(i, "?")) for i in attendees), key=lambda p: p.name),
            )

        @app.get(f"{PREFIX}/mine", response_model=list[ClipOut])
        def my_clips(m: Member = member, s: Session = db):
            return self._clips_out(s, m, client.my_clips(s, m))

        @app.get(f"{PREFIX}/to-check", response_model=list[ClipOut])
        def to_check(m: Member = member, s: Session = db):
            coach(m)
            return self._clips_out(s, m, client.to_check(s, m.org_id))

        @app.get(f"{PREFIX}/clips/{{clip_id}}", response_model=ClipOut)
        def get_clip(clip_id: int, m: Member = member, s: Session = db):
            return self._clips_out(s, m, [guard(lambda: client.clip(s, m, clip_id))])[0]

        @app.put(f"{PREFIX}/clips/{{clip_id}}/participants", response_model=ClipOut)
        def set_participants(clip_id: int, body: ParticipantsUpdate, m: Member = member, s: Session = db):
            clip = guard(lambda: client.set_participants(s, m, clip_id, body.people))
            return self._clips_out(s, m, [clip])[0]

        @app.post(f"{PREFIX}/clips/{{clip_id}}/validate", response_model=ClipOut)
        def validate(clip_id: int, m: Member = member, s: Session = db):
            return self._clips_out(s, m, [guard(lambda: client.validate(s, m, clip_id))])[0]

        @app.delete(f"{PREFIX}/clips/{{clip_id}}", status_code=204)
        def delete_clip(clip_id: int, m: Member = member, s: Session = db):
            guard(lambda: client.delete_clip(s, m, clip_id))

        @app.get(f"{PREFIX}/people", response_model=list[PersonOut])
        def people(m: Member = member, s: Session = db):
            """« Un autre membre… » : tous les membres actuels."""
            coach(m)
            return [PersonOut(id=p.id, name=p.name) for p in client.directory.people(s, m.org_id)]

    # --- Mise en forme ---

    def _sessions_out(self, s: Session, m: Member, sessions: list[ClipSession]) -> list[SessionOut]:
        ids = [x.id for x in sessions]
        clips = self.client.clips_by_session(s, ids)
        videos = self.client.video_map(
            s, [c.video_id for x in ids for c in clips[x][:3]] + [x.raw_video_id for x in sessions]
        )
        out = []
        for x in sessions:
            raw = videos.get(x.raw_video_id)
            status = "uploading" if raw is not None and raw.statut == "en_cours" else x.status
            out.append(
                SessionOut(
                    id=x.id,
                    title=x.title,
                    held_on=x.held_on,
                    status=status,
                    clip_count=len(clips[x.id]),
                    to_check_count=sum(c.to_check for c in clips[x.id]),
                    previews=[VideoSortie.model_validate(videos[c.video_id]) for c in clips[x.id][:3] if c.video_id in videos],
                    raw_video=VideoSortie.model_validate(raw) if raw is not None else None,
                )
            )
        return out

    def _clips_out(self, s: Session, m: Member, clips: list[Clip]) -> list[ClipOut]:
        if not clips:
            return []
        client = self.client
        people = client.participants(s, [c.id for c in clips])
        names = client.directory.names(s, m.org_id, {p for ps in people.values() for p in ps if p is not None})
        videos = client.video_map(s, [c.video_id for c in clips])
        sessions = {c.session_id: s.get(ClipSession, c.session_id) for c in clips}
        # Le rang d'une paire dans sa séance, pour « … vs … 2 ».
        order = client.clips_by_session(s, list(sessions))
        rank: dict[int, int] = {}
        for session_clips in order.values():
            seen: dict[tuple, int] = {}
            pairs = client.participants(s, [c.id for c in session_clips])
            for c in session_clips:
                key = tuple(sorted(p for p in pairs[c.id] if p is not None))
                seen[key] = seen.get(key, 0) + 1
                rank[c.id] = seen[key] if key else 1
        out = []
        for c in clips:
            ps = people[c.id]
            shown = [names.get(p) if p is not None else None for p in ps]
            video = videos.get(c.video_id)
            out.append(
                ClipOut(
                    id=c.id,
                    session_id=c.session_id,
                    position=c.position,
                    title=clip_title(shown, rank.get(c.id, 1)),
                    to_check=c.to_check,
                    check_reason=c.check_reason,
                    participants=[ParticipantOut(person_id=p, name=n) for p, n in zip(ps, shown)],
                    video=VideoSortie.model_validate(video) if video is not None else None,
                    session_title=sessions[c.session_id].title,
                    held_on=sessions[c.session_id].held_on,
                )
            )
        return out
