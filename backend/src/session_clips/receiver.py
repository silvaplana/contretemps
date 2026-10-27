"""Routes REST du module session_clips (/session-clips/...). Qui appelle est
fourni par l'appli hôte (`current_member`, une dépendance FastAPI qui
renvoie un `Member`) ; les droits sont vérifiés par le service."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_db
from videos.schemas import VideoSortie
from videos.videos import DecalageInvalide

from . import camera
from .models import Clip, ClipSession, Piece
from .ports import Member
from .schemas import (
    CameraOut,
    CameraStart,
    PieceOpen,
    PieceOut,
    RecorderHeartbeat,
    RecorderOrders,
    RecorderPair,
    RecorderPaired,
    SignalUpdate,
    ClipOut,
    FavoriteUpdate,
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

        @app.get(f"{PREFIX}/favorites", response_model=list[ClipOut])
        def favorites(m: Member = member, s: Session = db):
            return self._clips_out(s, m, client.favorites(s, m))

        @app.put(f"{PREFIX}/clips/{{clip_id}}/favorite", response_model=ClipOut)
        def set_favorite(clip_id: int, body: FavoriteUpdate, m: Member = member, s: Session = db):
            return self._clips_out(s, m, [guard(lambda: client.set_favorite(s, m, clip_id, body.favorite))])[0]

        @app.delete(f"{PREFIX}/clips/{{clip_id}}", status_code=204)
        def delete_clip(clip_id: int, m: Member = member, s: Session = db):
            guard(lambda: client.delete_clip(s, m, clip_id))

        @app.get(f"{PREFIX}/people", response_model=list[PersonOut])
        def people(m: Member = member, s: Session = db):
            """« Un autre membre… » : tous les membres actuels."""
            coach(m)
            return [PersonOut(id=p.id, name=p.name) for p in client.directory.people(s, m.org_id)]

        # --- Caméra de la salle (étape 3), côté coachs ---

        @app.get(f"{PREFIX}/camera", response_model=CameraOut)
        def camera_status(m: Member = member, s: Session = db):
            return CameraOut(**vars(guard(lambda: camera.status(s, m))))

        @app.post(f"{PREFIX}/camera/pairing-code", response_model=CameraOut)
        def pairing_code(m: Member = member, s: Session = db):
            guard(lambda: camera.new_pairing_code(s, m))
            return CameraOut(**vars(camera.status(s, m)))

        @app.post(f"{PREFIX}/camera/start", response_model=CameraOut)
        def camera_start(body: CameraStart, m: Member = member, s: Session = db):
            guard(lambda: camera.start(s, m, body.title.strip()))
            return CameraOut(**vars(camera.status(s, m)))

        @app.post(f"{PREFIX}/camera/stop", response_model=CameraOut)
        def camera_stop(m: Member = member, s: Session = db):
            guard(lambda: camera.stop(s, m))
            return CameraOut(**vars(camera.status(s, m)))

        @app.put(f"{PREFIX}/camera/signal", response_model=CameraOut)
        def camera_signal(body: SignalUpdate, m: Member = member, s: Session = db):
            guard(lambda: camera.set_signal(s, m, body.signal))
            return CameraOut(**vars(camera.status(s, m)))

        # --- Caméra de la salle, côté téléphone : sans session, avec le
        # jeton du jumelage (routes publiques, voir comptes/rbac.py) ---

        def recorder(s: Session, token: str | None):
            return guard(lambda: camera.recorder_for_token(s, token))

        @app.post(f"{PREFIX}/recorder/pair", response_model=RecorderPaired)
        def recorder_pair(body: RecorderPair, s: Session = db):
            _, token = guard(lambda: camera.pair(s, body.code))
            return RecorderPaired(token=token)

        @app.post(f"{PREFIX}/recorder/heartbeat", response_model=RecorderOrders)
        def recorder_heartbeat(body: RecorderHeartbeat, s: Session = db, x_recorder_token: str | None = Header(None)):
            r = recorder(s, x_recorder_token)
            camera.heartbeat(s, r, body.state, body.battery_percent, body.free_bytes, body.pending_pieces)
            return RecorderOrders(session_id=r.session_id, signal=r.signal)

        @app.post(f"{PREFIX}/recorder/pieces", response_model=PieceOut)
        def recorder_piece(body: PieceOpen, s: Session = db, x_recorder_token: str | None = Header(None)):
            r = recorder(s, x_recorder_token)
            piece = guard(lambda: camera.open_piece(s, client, r, body.session_id, body.position, body.size, body.last))
            return self._piece_out(s, piece)

        @app.get(f"{PREFIX}/recorder/pieces/{{upload_id}}", response_model=PieceOut)
        def recorder_piece_state(upload_id: str, s: Session = db, x_recorder_token: str | None = Header(None)):
            r = recorder(s, x_recorder_token)
            return self._piece_out(s, guard(lambda: camera.piece_of(s, r, upload_id)))

        @app.put(f"{PREFIX}/recorder/pieces/{{upload_id}}", response_model=PieceOut)
        async def recorder_piece_block(
            upload_id: str, request: Request, s: Session = db, x_recorder_token: str | None = Header(None)
        ):
            r = recorder(s, x_recorder_token)
            piece = guard(lambda: camera.piece_of(s, r, upload_id))
            data = await request.body()
            offset = int(request.headers.get("X-Decalage", "-1"))
            try:
                written = client.videos.ecrire_bloc(s, upload_id, offset, data)
            except DecalageInvalide as err:
                raise HTTPException(status_code=409, detail={"octets_recus": err.octets_recus}) from err
            if written is None:
                # Envoi interrompu plus d'un jour et nettoyé : le téléphone le rouvre.
                raise HTTPException(status_code=404, detail="Envoi expiré")
            camera.piece_written(s, r)
            return self._piece_out(s, piece)

    # --- Mise en forme ---

    def _piece_out(self, s: Session, piece: Piece) -> PieceOut:
        upload = self.client.videos.obtenir_televersement(s, piece.upload_id)
        return PieceOut(upload_id=piece.upload_id, received=upload.octets_recus if upload else 0)

    def _sessions_out(self, s: Session, m: Member, sessions: list[ClipSession]) -> list[SessionOut]:
        ids = [x.id for x in sessions]
        clips = self.client.clips_by_session(s, ids)
        videos = self.client.video_map(
            s, [c.video_id for x in ids for c in clips[x][:3]] + [x.raw_video_id for x in sessions]
        )
        live = set(s.scalars(select(Piece.session_id).where(Piece.session_id.in_(ids))))
        out = []
        for x in sessions:
            raw = videos.get(x.raw_video_id)
            status = "uploading" if raw is not None and raw.statut == "en_cours" else x.status
            out.append(
                SessionOut(
                    id=x.id,
                    title=x.title,
                    live=x.id in live,
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
        favorites = client.favorite_ids(s, m.person_id, [c.id for c in clips])
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
                    favorite=c.id in favorites,
                    check_reason=c.check_reason,
                    participants=[ParticipantOut(person_id=p, name=n) for p, n in zip(ps, shown)],
                    video=VideoSortie.model_validate(video) if video is not None else None,
                    session_title=sessions[c.session_id].title,
                    held_on=sessions[c.session_id].held_on,
                )
            )
        return out
