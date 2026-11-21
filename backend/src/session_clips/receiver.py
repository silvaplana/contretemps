"""Routes REST du module session_clips (/session-clips/...). Qui appelle est
fourni par l'appli hôte (`current_member`, une dépendance FastAPI qui
renvoie un `Member`) ; les droits sont vérifiés par le service."""

from __future__ import annotations

import json
from datetime import date
from collections.abc import Callable

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_db
from videos.schemas import VideoSortie
from videos.videos import DecalageInvalide

from . import announcer, camera, gesture_notes, lab, voice
from . import people as who_is
from .models import Clip, ClipSession, LabTest, Piece
from .ports import Member
from .schemas import (
    FilmPart,
    CameraOut,
    ClubSignsBody,
    LabFightOut,
    LabSignOut,
    LabTestCreate,
    LabTestDetail,
    LabTestRename,
    LabTestOut,
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
    GestureNote,
    MeOut,
    ParticipantOut,
    ParticipantsUpdate,
    PeopleOut,
    PersonName,
    PersonOut,
    FoundPerson,
    Proposal,
    SessionCreate,
    SessionDetail,
    SessionOut,
    SessionRename,
    ThisPhone,
    VoiceAnswer,
    VoiceMissing,
    VoiceNote,
)
from .service import OUTSIDER_NAME, ForbiddenError, NotFoundError, SessionClips, clip_title

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
            return self._clips_out(s, m, [guard(lambda: client.add_fight(s, m, body.upload_id, body.people, body.winner, body.draw, body.overlay.model_dump() if body.overlay else None))])[0]

        @app.patch(f"{PREFIX}/sessions/{{session_id}}", response_model=SessionOut)
        def rename_session(session_id: int, body: SessionRename, m: Member = member, s: Session = db):
            session = guard(lambda: client.rename_session(s, m, session_id, body.title.strip()))
            return self._sessions_out(s, m, [session])[0]

        @app.post(f"{PREFIX}/sessions/{{session_id}}/recut", status_code=204)
        def recut_session(session_id: int, m: Member = member, s: Session = db):
            guard(lambda: client.recut_session(s, m, session_id))

        @app.delete(f"{PREFIX}/sessions/{{session_id}}", status_code=204)
        def delete_session(session_id: int, m: Member = member, s: Session = db):
            guard(lambda: client.delete_session(s, m, session_id))

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
                signs=json.loads(session.signs) if session.signs else [],
                film=self._film(s, session),
            )

        # Qui est qui ? (Seb, 17/11) : les personnes repérées dans les combats.
        @app.get(f"{PREFIX}/sessions/{{session_id}}/people", response_model=PeopleOut)
        def session_people(session_id: int, m: Member = member, s: Session = db):
            coach(m)
            session = guard(lambda: client.session(s, m, session_id))
            return self._people_out(s, m, session, who_is.load(session.org_id, session.id))

        @app.get(f"{PREFIX}/sessions/{{session_id}}/names", response_model=list[PersonOut])
        def session_names(session_id: int, m: Member = member, s: Session = db):
            """Choisir un nom : tous les membres, ceux de la séance et des mêmes
            jours des semaines d'avant en tête (Seb, 17/11)."""
            coach(m)
            session = guard(lambda: client.session(s, m, session_id))
            names = {p.id: p.name for p in client.directory.people(s, m.org_id)}
            return [PersonOut(id=i, name=names[i]) for i in client.name_order(s, session)]

        @app.put(f"{PREFIX}/sessions/{{session_id}}/people/{{number}}", response_model=PeopleOut)
        def name_person(session_id: int, number: int, body: PersonName, m: Member = member, s: Session = db):
            coach(m)
            session = guard(lambda: client.session(s, m, session_id))
            if isinstance(body.who, int) and body.who not in {p.id for p in client.directory.people(s, m.org_id)}:
                raise HTTPException(status_code=400, detail="Ce membre n'est pas de l'organisation")
            try:
                data = who_is.name(s, session, number, body.who)
            except LookupError as err:
                raise HTTPException(status_code=404, detail=str(err)) from err
            return self._people_out(s, m, session, data)

        # Noter les cris d'une séance filmée (étude du 14/11), pour le rejeu.
        @app.get(f"{PREFIX}/sessions/{{session_id}}/voice-notes")
        def session_voice_notes(session_id: int, m: Member = member, s: Session = db):
            guard(lambda: client.session(s, m, session_id))
            return guard(lambda: voice.session_truth(m, session_id))

        @app.post(f"{PREFIX}/sessions/{{session_id}}/voice-notes", status_code=201)
        def note_session_voice(session_id: int, body: VoiceNote, m: Member = member, s: Session = db):
            session = guard(lambda: client.session(s, m, session_id))
            pieces = self._sources(s, session)
            return guard(lambda: voice.note_session(m, session_id, pieces, body.t, body.answer, body.word))

        @app.delete(f"{PREFIX}/sessions/{{session_id}}/voice-notes")
        def unnote_session_voice(session_id: int, t: float, m: Member = member, s: Session = db):
            guard(lambda: client.session(s, m, session_id))
            return guard(lambda: voice.unnote_session(m, session_id, t))

        # Noter les gestes dans la frise (Seb, 15/11), pour « Proposer un réglage ».
        @app.get(f"{PREFIX}/sessions/{{session_id}}/gesture-notes")
        def session_gesture_notes(session_id: int, m: Member = member, s: Session = db):
            guard(lambda: client.session(s, m, session_id))
            return guard(lambda: gesture_notes.notes(m, session_id))

        @app.post(f"{PREFIX}/sessions/{{session_id}}/gesture-notes", status_code=201)
        def note_session_gesture(session_id: int, body: GestureNote, m: Member = member, s: Session = db):
            guard(lambda: client.session(s, m, session_id))
            return guard(lambda: gesture_notes.note(m, session_id, body.t, body.kind, body.answer, body.real))

        @app.delete(f"{PREFIX}/sessions/{{session_id}}/gesture-notes")
        def unnote_session_gesture(session_id: int, t: float, m: Member = member, s: Session = db):
            guard(lambda: client.session(s, m, session_id))
            return guard(lambda: gesture_notes.unnote(m, session_id, t))

        @app.get(f"{PREFIX}/signs/proposal")
        def propose_signs(m: Member = member, s: Session = db):
            from .cutting import session_frames

            noted = guard(lambda: gesture_notes.noted_sessions(m))
            sessions = []
            for session_id, marks in noted.items():
                session = s.get(ClipSession, session_id)
                if session is not None and session.org_id == m.org_id:
                    sessions.append((session_frames(s, session), marks))
            return gesture_notes.propose(sessions, lab.settings(s, m.org_id).min_hold)

        @app.get(f"{PREFIX}/mine", response_model=list[ClipOut])
        def my_clips(m: Member = member, s: Session = db):
            return self._clips_out(s, m, client.my_clips(s, m))

        @app.get(f"{PREFIX}/to-check", response_model=list[ClipOut])
        def to_check(m: Member = member, s: Session = db):
            coach(m)
            return self._clips_out(s, m, client.to_check(s, m.org_id))

        @app.get(f"{PREFIX}/clips/{{clip_id}}", response_model=ClipOut)
        def get_clip(clip_id: int, m: Member = member, s: Session = db):
            clip = guard(lambda: client.clip(s, m, clip_id))
            client.mark_viewed(s, m, clip)
            return self._clips_out(s, m, [clip])[0]

        @app.get(f"{PREFIX}/new")
        def new_clips(m: Member = member, s: Session = db):
            """La pastille de Fights (Seb, 17/11) : combats validés pas encore ouverts."""
            return {"count": client.new_count(s, m)}

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

        # Timer étendu (Seb, 21/11) : le choix du combattant, ★ les habitués de ce jour de la semaine.
        @app.get(f"{PREFIX}/timer/names", response_model=list[PersonOut])
        def timer_names(m: Member = member, s: Session = db):
            coach(m)
            names = {p.id: p.name for p in client.directory.people(s, m.org_id)}
            regulars = set(client.regulars(s, m.org_id, date.today()))
            return [PersonOut(id=i, name=names[i], regular=i in regulars) for i in client.timer_order(s, m.org_id, date.today())]

        # L'annonce du vainqueur : son nom dit par George.
        @app.get(f"{PREFIX}/timer/announce/{{person_id}}")
        def announce(person_id: int, m: Member = member, s: Session = db):
            coach(m)
            full_name = client.directory.full_name(s, m.org_id, person_id)
            if not full_name:
                raise HTTPException(status_code=404, detail="Membre introuvable")
            try:
                return FileResponse(announcer.name_file(m.org_id, person_id, full_name), media_type="audio/mpeg")
            except announcer.VoiceUnavailable as e:
                raise HTTPException(status_code=503, detail=str(e)) from e

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

        @app.post(f"{PREFIX}/camera/this-phone", response_model=ThisPhone)
        def camera_this_phone(m: Member = member, s: Session = db):
            return ThisPhone(token=guard(lambda: camera.pair_this_phone(s, m)))

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

        # --- Labo (§6.5 bis) : essais sur des vidéos déjà filmées, coachs ---

        def settings_out(x: lab.Settings) -> ClubSignsBody:
            return ClubSignsBody(
                signs=list(x.signs), framing=x.framing, start_skip=x.start_skip, end_skip=x.end_skip, show_timeline=x.show_timeline,
                loud_only=x.loud_only, sure_only=x.sure_only, loud_db=x.loud_db, sure_min=x.sure_min,
                speech_model=x.speech_model, min_hold=x.min_hold,
            )

        @app.get(f"{PREFIX}/signs", response_model=ClubSignsBody)
        def club_signs(m: Member = member, s: Session = db):
            coach(m)
            return settings_out(lab.settings(s, m.org_id))

        @app.put(f"{PREFIX}/signs", response_model=ClubSignsBody)
        def set_club_signs(body: ClubSignsBody, m: Member = member, s: Session = db):
            new = lab.Settings(
                tuple(body.signs), body.framing, body.start_skip, body.end_skip, body.show_timeline,
                body.loud_only, body.sure_only, body.loud_db, body.sure_min, body.speech_model, body.min_hold,
            )
            return settings_out(guard(lambda: lab.set_settings(s, m, new)))

        # Les réglages du Labo, à part de ceux du tournage (Seb, 12/11).
        @app.get(f"{PREFIX}/lab/signs", response_model=ClubSignsBody)
        def lab_signs(m: Member = member, s: Session = db):
            coach(m)
            return settings_out(lab.settings(s, m.org_id, lab=True))

        @app.put(f"{PREFIX}/lab/signs", response_model=ClubSignsBody)
        def set_lab_signs(body: ClubSignsBody, m: Member = member, s: Session = db):
            new = lab.Settings(
                tuple(body.signs), body.framing, body.start_skip, body.end_skip, body.show_timeline,
                body.loud_only, body.sure_only, body.loud_db, body.sure_min, body.speech_model, body.min_hold,
            )
            return settings_out(guard(lambda: lab.set_settings(s, m, new, lab=True)))

        # Fights › ⋮ › Entraîner l'écoute (Seb, 14/11) : les cris enregistrés au téléphone.
        @app.get(f"{PREFIX}/voice", response_model=dict[str, list[str]])
        def voice_samples(m: Member = member):
            return guard(lambda: voice.samples(m))

        @app.delete(f"{PREFIX}/voice", status_code=204)
        def reset_voice(m: Member = member):
            guard(lambda: voice.reset(m))

        @app.post(f"{PREFIX}/voice/{{word}}", response_model=dict[str, list[str]], status_code=201)
        async def add_voice_sample(word: str, request: Request, m: Member = member):
            data = await request.body()
            return guard(lambda: voice.add(m, word, data, request.headers.get("content-type", "")))

        @app.get(f"{PREFIX}/voice/{{word}}/{{name}}")
        def voice_sample(word: str, name: str, m: Member = member):
            return FileResponse(guard(lambda: voice.path(m, word, name)))

        @app.delete(f"{PREFIX}/voice/{{word}}/{{name}}", status_code=204)
        def delete_voice_sample(word: str, name: str, m: Member = member):
            guard(lambda: voice.delete(m, word, name))

        @app.delete(f"{PREFIX}/voice-tests", status_code=204)
        def reset_voice_tests(m: Member = member):
            guard(lambda: voice.reset_tests(m))

        @app.post(f"{PREFIX}/voice-tests", status_code=201)
        async def add_voice_test(request: Request, m: Member = member):
            data = await request.body()
            return {"name": guard(lambda: voice.add_test(m, data, request.headers.get("content-type", "")))}

        @app.post(f"{PREFIX}/voice-tests/{{name}}/answer", status_code=204)
        def answer_voice_test(name: str, body: VoiceAnswer, m: Member = member):
            guard(lambda: voice.answer_test(m, name, body.t, body.answer, body.word))

        @app.post(f"{PREFIX}/voice-tests/{{name}}/missing", status_code=204)
        def missing_voice_word(name: str, body: VoiceMissing, m: Member = member):
            guard(lambda: voice.missing_word(m, name, body.word))

        @app.post(f"{PREFIX}/voice-replays", status_code=201)
        def add_voice_replay(m: Member = member):
            guard(lambda: voice.add_replay(m))

        @app.get(f"{PREFIX}/voice-replays")
        def voice_replays(m: Member = member):
            return guard(lambda: voice.replays(m))

        @app.get(f"{PREFIX}/voice-tests/{{name}}")
        def voice_test(name: str, m: Member = member):
            return guard(lambda: voice.test_result(m, name))

        @app.get(f"{PREFIX}/lab", response_model=list[LabTestOut])
        def lab_tests(m: Member = member, s: Session = db):
            return [self._lab_out(s, t) for t in guard(lambda: lab.tests(s, m))]

        @app.post(f"{PREFIX}/lab", response_model=LabTestOut, status_code=201)
        def create_lab_test(body: LabTestCreate, m: Member = member, s: Session = db):
            return self._lab_out(s, guard(lambda: lab.create_test(s, client, m, body.upload_id, body.title.strip())))

        @app.get(f"{PREFIX}/lab/{{test_id}}", response_model=LabTestDetail)
        def get_lab_test(test_id: int, m: Member = member, s: Session = db):
            found = guard(lambda: lab.test(s, m, test_id))
            return LabTestDetail(
                **self._lab_out(s, found).model_dump(),
                signs=[LabSignOut(**x) for x in lab.signs_of(found)],
                fights=[
                    LabFightOut(
                        start=f.start,
                        end=f.end,
                        fighters=f.fighters,
                        check_reason=f.check_reason,
                        frame=[list(b) for b in frame] if frame else None,
                    )
                    for f, frame in lab.fights_of(s, found)
                ],
            )

        @app.post(f"{PREFIX}/lab/{{test_id}}/reread", status_code=204)
        def reread_lab_test(test_id: int, m: Member = member, s: Session = db):
            guard(lambda: lab.reread_test(s, client, m, test_id))

        @app.patch(f"{PREFIX}/lab/{{test_id}}", response_model=LabTestOut)
        def rename_lab_test(test_id: int, body: LabTestRename, m: Member = member, s: Session = db):
            return self._lab_out(s, guard(lambda: lab.rename_test(s, m, test_id, body.title.strip())))

        @app.delete(f"{PREFIX}/lab/{{test_id}}", status_code=204)
        def delete_lab_test(test_id: int, m: Member = member, s: Session = db):
            guard(lambda: lab.delete_test(s, client, m, test_id))

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

        @app.put(f"{PREFIX}/recorder/image", status_code=204)
        async def recorder_image(request: Request, s: Session = db, x_recorder_token: str | None = Header(None)):
            r = recorder(s, x_recorder_token)
            data = await request.body()
            guard(lambda: camera.save_image(r, data))

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

    def _people_out(self, s: Session, m: Member, session: ClipSession, data: dict | None) -> PeopleOut:
        clip_ids = [c.id for c in self.client.clips_by_session(s, [session.id])[session.id]]
        if data is None or data.get("clips") != clip_ids:
            return PeopleOut(ready=False, persons=[], filled=0, total=len(clip_ids))
        found = who_is.proposals(s, session, data)
        ids = {p["member"] for p in data["persons"] if isinstance(p["member"], int)} | {x[0] for x in found.values()}
        names = self.client.directory.names(s, m.org_id, ids)
        fights = {n: sum(n in places for places in data["places"].values()) for n in (p["n"] for p in data["persons"])}
        persons = [
            FoundPerson(
                n=p["n"],
                image=p["image"],
                label=who_is.outfit_label(p["shirt"], p["short"]),
                member_id=p["member"] if isinstance(p["member"], int) else None,
                outsider=p["member"] == who_is.OUTSIDER,
                name=OUTSIDER_NAME if p["member"] == who_is.OUTSIDER else names.get(p["member"]),
                fights=fights[p["n"]],
                proposal=Proposal(member_id=found[p["n"]][0], name=names.get(found[p["n"]][0], "?"), reason=found[p["n"]][1])
                if p["n"] in found
                else None,
            )
            for p in data["persons"]
        ]
        rows = self.client.participants(s, clip_ids)
        outsiders = self.client.outsiders(s, clip_ids)
        filled = sum(
            1 for c in clip_ids if rows[c] and all(p is not None or (c, i) in outsiders for i, p in enumerate(rows[c]))
        )
        return PeopleOut(ready=True, persons=persons, filled=filled, total=len(clip_ids))

    def _piece_out(self, s: Session, piece: Piece) -> PieceOut:
        upload = self.client.videos.obtenir_televersement(s, piece.upload_id)
        return PieceOut(upload_id=piece.upload_id, received=upload.octets_recus if upload else 0)

    def _lab_out(self, s: Session, found: LabTest) -> LabTestOut:
        video = self.client.video_map(s, [found.video_id]).get(found.video_id)
        status = "uploading" if video is not None and video.statut == "en_cours" else found.status
        return LabTestOut(
            id=found.id,
            title=found.title,
            status=status,
            created_at=found.created_at,
            video=VideoSortie.model_validate(video) if video is not None else None,
        )

    def _film(self, s: Session, session: ClipSession) -> list[FilmPart]:
        """Les morceaux arrivés de la caméra, dans l'ordre et sans trou (comme
        la découpe les recolle), sinon la vidéo envoyée à la main."""
        pieces = list(s.scalars(select(Piece).where(Piece.session_id == session.id).order_by(Piece.position)))
        ids = [p.video_id for p in pieces if p.video_id is not None] or [session.raw_video_id]
        videos = self.client.video_map(s, [i for i in ids if i is not None])
        out, offset = [], 0.0
        for p in pieces or [None]:
            video = videos.get(p.video_id if p else session.raw_video_id)
            if video is None or video.statut != "complete":
                break
            out.append(FilmPart(start=offset, video=VideoSortie.model_validate(video)))
            offset += (p.duration_seconds if p else None) or video.duree_secondes or 0
        return out

    def _sources(self, s: Session, session: ClipSession) -> list[tuple[str, float, float]]:
        """Les fichiers du film de la séance (chemin sous VIDEOS_DIR, début, durée), recollés comme `_film`."""
        pieces = list(s.scalars(select(Piece).where(Piece.session_id == session.id).order_by(Piece.position)))
        ids = [p.video_id for p in pieces if p.video_id is not None] or [session.raw_video_id]
        videos = self.client.video_map(s, [i for i in ids if i is not None])
        out, offset = [], 0.0
        for p in pieces or [None]:
            video = videos.get(p.video_id if p else session.raw_video_id)
            if video is None or video.statut != "complete":
                break
            length = (p.duration_seconds if p else None) or video.duree_secondes or 0
            out.append((video.lien_fichier, offset, float(length)))
            offset += length
        return out

    def _sessions_out(self, s: Session, m: Member, sessions: list[ClipSession]) -> list[SessionOut]:
        ids = [x.id for x in sessions]
        clips = self.client.clips_by_session(s, ids)
        pieces: dict[int, list[Piece]] = {}
        for p in s.scalars(select(Piece).where(Piece.session_id.in_(ids)).order_by(Piece.position)):
            pieces.setdefault(p.session_id, []).append(p)
        # La vignette : le premier morceau de la caméra, sinon la vidéo envoyée à la main.
        covers = {
            x.id: next((p.video_id for p in pieces.get(x.id, []) if p.video_id is not None), x.raw_video_id) for x in sessions
        }
        videos = self.client.video_map(
            s, [c.video_id for x in ids for c in clips[x][:3]] + [x.raw_video_id for x in sessions] + list(covers.values())
        )
        uploads = {p.upload_id: self.client.videos.obtenir_televersement(s, p.upload_id) for ps in pieces.values() for p in ps}
        sending = {k: [u for p in ps if (u := uploads[p.upload_id]) is not None and not u.complet] for k, ps in pieces.items()}
        online = camera.online(s, m.org_id)
        out = []
        for x in sessions:
            raw = videos.get(x.raw_video_id)
            status = "uploading" if raw is not None and raw.statut == "en_cours" else x.status
            out.append(
                SessionOut(
                    id=x.id,
                    title=x.title,
                    live=x.id in pieces,
                    held_on=x.held_on,
                    status=status,
                    clip_count=len(clips[x.id]),
                    to_check_count=sum(c.to_check for c in clips[x.id]),
                    previews=[VideoSortie.model_validate(videos[c.video_id]) for c in clips[x.id][:3] if c.video_id in videos],
                    raw_video=VideoSortie.model_validate(raw) if raw is not None else None,
                    cover=VideoSortie.model_validate(videos[covers[x.id]]) if covers[x.id] in videos else None,
                    # Filmée par la caméra (pas de vidéo envoyée à la main) : début et fin, toujours.
                    started_at=x.created_at if x.id in pieces or x.raw_video_id is None else None,
                    ended_at=x.ended_at,
                    filmed_seconds=sum(p.duration_seconds or 0 for p in pieces.get(x.id, [])),
                    pieces_read=sum(p.duration_seconds is not None for p in pieces.get(x.id, [])),
                    pieces_total=len(pieces.get(x.id, [])),
                    sent_bytes=sum(u.octets_recus for u in sending.get(x.id, [])),
                    size_bytes=sum(u.octets_total for u in sending.get(x.id, [])),
                    camera_online=online,
                )
            )
        return out

    def _clips_out(self, s: Session, m: Member, clips: list[Clip]) -> list[ClipOut]:
        if not clips:
            return []
        client = self.client
        people = client.participants(s, [c.id for c in clips])
        outsiders = client.outsiders(s, [c.id for c in clips])
        winners = client.winners(s, [c.id for c in clips])
        names = client.directory.names(s, m.org_id, {p for ps in people.values() for p in ps if p is not None})
        videos = client.video_map(s, [c.video_id for c in clips])
        favorites = client.favorite_ids(s, m.person_id, [c.id for c in clips])
        viewed = client.viewed_ids(s, m.person_id, [c.id for c in clips])
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
            out_slots = [(c.id, i) in outsiders for i in range(len(ps))]
            shown = [OUTSIDER_NAME if o else names.get(p) if p is not None else None for p, o in zip(ps, out_slots)]
            video = videos.get(c.video_id)
            out.append(
                ClipOut(
                    id=c.id,
                    session_id=c.session_id,
                    position=c.position,
                    title=clip_title(shown, rank.get(c.id, 1)),
                    to_check=c.to_check,
                    draw=c.draw,
                    preparing=c.overlay is not None,
                    favorite=c.id in favorites,
                    new=not c.to_check and m.person_id in ps and c.id not in viewed,
                    check_reason=c.check_reason,
                    participants=[
                        ParticipantOut(person_id=p, name=n, outsider=o, winner=(c.id, i) in winners)
                        for i, (p, n, o) in enumerate(zip(ps, shown, out_slots))
                    ],
                    video=VideoSortie.model_validate(video) if video is not None else None,
                    session_title=sessions[c.session_id].title,
                    held_on=sessions[c.session_id].held_on,
                    start_seconds=c.start_seconds,
                )
            )
        return out
