"""La caméra de la salle (spec/modules/video-combats.md §4 et §6.3, étape 3) :
jumelage du téléphone, ordres « Démarrer la séance » / « Fin de séance »,
état visible dans Fights et réception des morceaux de 2 minutes.

Le téléphone (appli Android « enregistreur », dossier `recorder/`) n'est pas
un membre : il s'identifie par un jeton remis au jumelage. Il demande toutes
les 5 s ce qu'il doit faire (`heartbeat`) ; il n'y a pas de notification à
lui envoyer.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import ClipSession, Piece, Recorder
from .ports import Member
from .service import ForbiddenError, NotFoundError, SessionClips, video_name

PAIRING_MINUTES = 10
# Sans nouvelles du téléphone depuis 30 s : « Hors service ».
OFFLINE_AFTER = timedelta(seconds=30)
SIGNALS = ("beep", "light", "both")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _require_coach(member: Member) -> None:
    if not member.is_coach:
        raise ForbiddenError("Réservé aux coachs")


def recorder_of(db: Session, org_id: int) -> Recorder | None:
    """Une seule caméra par organisation pour l'instant (§4)."""
    return db.scalar(select(Recorder).where(Recorder.org_id == org_id).order_by(Recorder.id.desc()))


# --- Jumelage ---


def new_pairing_code(db: Session, member: Member) -> Recorder:
    """« Installer la caméra » : un code de 8 chiffres valable 10 minutes. Le
    téléphone déjà jumelé, s'il y en a un, est remplacé quand le nouveau
    tape le code."""
    _require_coach(member)
    recorder = recorder_of(db, member.org_id)
    if recorder is None or recorder.token_hash is not None:
        recorder = Recorder(org_id=member.org_id)
        db.add(recorder)
    recorder.pairing_code = f"{secrets.randbelow(10**8):08d}"
    recorder.pairing_expires_at = _now() + timedelta(minutes=PAIRING_MINUTES)
    db.commit()
    return recorder


def pair(db: Session, code: str) -> tuple[Recorder, str]:
    """Le téléphone tape le code : il reçoit son jeton, qui ne sera plus
    jamais montré. Les anciens téléphones de l'organisation sont oubliés."""
    code = "".join(c for c in code if c.isdigit())
    recorder = db.scalar(select(Recorder).where(Recorder.pairing_code == code, Recorder.pairing_expires_at > _now()))
    if recorder is None or len(code) != 8:
        raise NotFoundError("Code inconnu ou expiré")
    for old in db.scalars(select(Recorder).where(Recorder.org_id == recorder.org_id, Recorder.id != recorder.id)):
        db.delete(old)
    token = secrets.token_urlsafe(32)
    recorder.token_hash = _hash(token)
    recorder.pairing_code = None
    recorder.pairing_expires_at = None
    recorder.last_seen_at = _now()
    db.commit()
    return recorder, token


def recorder_for_token(db: Session, token: str | None) -> Recorder:
    recorder = db.scalar(select(Recorder).where(Recorder.token_hash == _hash(token))) if token else None
    if recorder is None:
        raise ForbiddenError("Caméra inconnue : jumelez-la de nouveau")
    return recorder


# --- Le téléphone ---


def heartbeat(
    db: Session, recorder: Recorder, state: str, battery_percent: int | None, free_bytes: int | None, pending_pieces: int
) -> Recorder:
    recorder.state = "recording" if state == "recording" else "ready"
    recorder.battery_percent = battery_percent
    recorder.free_bytes = free_bytes
    recorder.pending_pieces = max(0, pending_pieces)
    recorder.last_seen_at = _now()
    db.commit()
    return recorder


def open_piece(db: Session, clips: SessionClips, recorder: Recorder, session_id: int, position: int, size: int, last: bool) -> Piece:
    """Un morceau fini : l'envoi par blocs du module `videos` est ouvert, et
    la vidéo sera complète au dernier bloc. Rejouable : le même morceau
    rouvert après une coupure reprend son envoi."""
    session = db.get(ClipSession, session_id)
    if session is None or session.org_id != recorder.org_id:
        raise NotFoundError("Séance introuvable")
    piece = db.scalar(select(Piece).where(Piece.session_id == session_id, Piece.position == position))
    if piece is not None and clips.videos.obtenir_televersement(db, piece.upload_id) is not None:
        piece.last = piece.last or last
        db.commit()
        return piece
    upload = clips.videos.creer_televersement(db, recorder.org_id, ".mp4", size)
    if piece is None:
        piece = Piece(session_id=session_id, position=position, upload_id=upload.id, last=last)
        db.add(piece)
    else:
        piece.upload_id = upload.id
        piece.last = piece.last or last
    db.flush()
    video = clips.videos.finaliser(
        db,
        upload.id,
        nom=video_name(session.held_on, session.title, f"morceau {position + 1}"),
        uploaded_by=session.created_by,
        deja_compresse=True,
    )
    piece.video_id = video.id
    db.commit()
    return piece


def piece_of(db: Session, recorder: Recorder, upload_id: str) -> Piece:
    piece = db.scalar(select(Piece).where(Piece.upload_id == upload_id))
    if piece is None or db.get(ClipSession, piece.session_id).org_id != recorder.org_id:
        raise NotFoundError("Morceau introuvable")
    return piece


def piece_written(db: Session, recorder: Recorder) -> None:
    recorder.last_upload_at = _now()
    db.commit()


# --- Les coachs (Fights) ---


@dataclass
class CameraStatus:
    paired: bool
    state: str  # 'none' | 'ready' | 'recording' | 'offline'
    battery_percent: int | None
    free_bytes: int | None
    pending_pieces: int
    last_upload_at: datetime | None
    session_id: int | None
    session_title: str
    started_at: datetime | None
    signal: str
    pairing_code: str | None
    pairing_expires_at: datetime | None


def status(db: Session, member: Member) -> CameraStatus:
    _require_coach(member)
    r = recorder_of(db, member.org_id)
    paired = r is not None and r.token_hash is not None
    if not paired:
        state = "none"
    elif r.last_seen_at is None or _now() - r.last_seen_at > OFFLINE_AFTER:
        state = "offline"
    else:
        # Demandé mais pas encore commencé : le téléphone démarre dans les 5 s.
        state = "recording" if r.session_id is not None or r.state == "recording" else "ready"
    session = db.get(ClipSession, r.session_id) if r is not None and r.session_id else None
    pending = r is not None and r.pairing_code is not None and r.pairing_expires_at > _now()
    return CameraStatus(
        paired=paired,
        state=state,
        battery_percent=r.battery_percent if paired else None,
        free_bytes=r.free_bytes if paired else None,
        pending_pieces=r.pending_pieces if paired else 0,
        last_upload_at=r.last_upload_at if paired else None,
        session_id=session.id if session else None,
        session_title=session.title if session else "",
        started_at=r.started_at if session else None,
        signal=r.signal if r is not None else "beep",
        pairing_code=r.pairing_code if pending else None,
        pairing_expires_at=r.pairing_expires_at if pending else None,
    )


def _paired(db: Session, member: Member) -> Recorder:
    _require_coach(member)
    r = recorder_of(db, member.org_id)
    if r is None or r.token_hash is None:
        raise NotFoundError("Aucune caméra installée")
    return r


def start(db: Session, member: Member, title: str) -> ClipSession:
    """« Démarrer la séance » : une séance « Filme » ; le téléphone commence
    à sa prochaine demande."""
    r = _paired(db, member)
    if r.session_id is not None:
        return db.get(ClipSession, r.session_id)
    session = ClipSession(
        org_id=member.org_id, title=title, held_on=date.today(), status="recording", created_by=member.person_id
    )
    db.add(session)
    db.flush()
    r.session_id = session.id
    r.started_at = _now()
    db.commit()
    return session


def stop(db: Session, member: Member) -> ClipSession | None:
    """« Fin de séance » : le téléphone finit son morceau en cours, l'envoie
    marqué « dernier » ; la découpe termine la séance (cutting.py)."""
    r = _paired(db, member)
    session = db.get(ClipSession, r.session_id) if r.session_id else None
    if session is not None and session.status == "recording":
        session.status = "processing"
        # Arrêtée avant que le téléphone ait commencé : rien n'a été filmé.
        if r.state != "recording" and piece_count(db, session.id) == 0:
            db.delete(session)
            session = None
    r.session_id = None
    r.started_at = None
    db.commit()
    return session


def set_signal(db: Session, member: Member, signal: str) -> None:
    if signal not in SIGNALS:
        raise ValueError("Signal inconnu")
    r = _paired(db, member)
    r.signal = signal
    db.commit()


def piece_count(db: Session, session_id: int) -> int:
    return db.scalar(select(func.count()).select_from(Piece).where(Piece.session_id == session_id)) or 0
