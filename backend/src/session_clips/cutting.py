"""Découpe d'une séance en clips (spec/modules/video-combats.md §5, étape 2),
lancée par le conteneur `sparring-worker` (app/sparring_worker.py).

Deux cas : la vidéo entière envoyée à la main (`cut_session`, la nuit), et
les morceaux de 2 minutes de la caméra de la salle (`cut_live`, au fil du
cours, étape 3).

Pour chaque combat repéré (fights.py), ffmpeg coupe un clip en 720p, le
range dans le module `videos` puis dans la séance (`SessionClips.add_clip`).
Les noms ne sont pas encore reconnus (V3) : chaque clip part dans
« À vérifier ». La vidéo brute est gardée jusqu'à la validation.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from collections.abc import Callable, Iterable
from pathlib import Path
from uuid import uuid4

import imageio_ffmpeg
from sqlalchemy import select
from sqlalchemy.orm import Session

from saisons.portee import toutes_saisons
from videos import Video
from videos.duree import duree_secondes
from videos.poster import generer_poster
from videos.stockage import DOSSIER_VIDEOS_LIVE, chemin_relatif, dossier_ecole

from .fights import REASON_NO_END, find_fights
from .models import Clip, ClipSession, Piece
from .service import SessionClips, video_name
from .signals import Frame, Pose

CLIP_HEIGHT = 720
REASON_NAMES = "Choisissez les noms des combattants."

Detector = Callable[[Path], Iterable[Frame]]


def sessions_to_cut(db: Session) -> list[ClipSession]:
    """Les séances dont la vidéo brute est arrivée en entier."""
    with toutes_saisons(db):
        return list(
            db.scalars(
                select(ClipSession)
                .join(Video, Video.id == ClipSession.raw_video_id)
                .where(ClipSession.status == "processing", Video.statut == "complete")
                .order_by(ClipSession.id)
            )
        )


def cut_clip(source: Path, start: float, end: float, dest: Path) -> bool:
    return _ffmpeg(["-ss", f"{start:.2f}", "-i", str(source)], end - start, dest)


def _ffmpeg(inputs: list[str], length: float, dest: Path) -> bool:
    try:
        result = subprocess.run(
            [
                imageio_ffmpeg.get_ffmpeg_exe(),
                "-y",
                *inputs,
                "-t", f"{length:.2f}",
                "-vf", f"scale=-2:'min({CLIP_HEIGHT},ih)'",
                "-c:v", "libx264",
                "-crf", "26",
                "-preset", "veryfast",
                "-c:a", "aac",
                "-b:a", "96k",
                str(dest),
            ],
            capture_output=True,
            timeout=1800,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and dest.exists()


def cut_session(db: Session, clips: SessionClips, session: ClipSession, detect: Detector) -> int:
    """Découpe une séance et la passe à `ready` ; renvoie le nombre de clips.
    Rejouable : les clips d'un essai interrompu sont d'abord effacés."""
    with toutes_saisons(db):
        for video_id in db.scalars(select(Clip.video_id).where(Clip.session_id == session.id)).all():
            clips.videos.delete(db, video_id)
        raw = clips.videos.get(db, session.raw_video_id)
    source = DOSSIER_VIDEOS_LIVE / raw.lien_fichier
    fights = find_fights(list(detect(source)))

    folder = dossier_ecole(session.org_id)
    count = 0
    for fight in fights:
        name = f"{uuid4().hex}.mp4"
        dest = folder / name
        if not cut_clip(source, fight.start, fight.end, dest):
            continue
        poster = folder / f"{dest.stem}.jpg"
        video = clips.videos.create(
            db,
            ecole_id=session.org_id,
            nom=video_name(session.held_on, session.title, f"combat {count + 1}"),
            lien_fichier=chemin_relatif(session.org_id, name),
            poster=chemin_relatif(session.org_id, poster.name) if generer_poster(dest, poster) else None,
            uploaded_by=session.created_by,
            duree_secondes=duree_secondes(dest),
            compresse=True,
        )
        clips.add_clip(
            db, session.id, video.id, [None] * fight.fighters, check_reason=fight.check_reason or REASON_NAMES
        )
        count += 1
    session.status = "ready"
    db.commit()
    return count


# --- Caméra de la salle : morceaux de 2 minutes (étape 3) ---

_RE_DURATION = re.compile(r"Duration:\s*(\d+):(\d{2}):(\d{2}\.\d+)")


def live_sessions(db: Session) -> list[ClipSession]:
    """Les séances filmées par la caméra de la salle pas encore finies."""
    with toutes_saisons(db):
        return list(
            db.scalars(
                select(ClipSession)
                .where(ClipSession.status.in_(("recording", "processing")), ClipSession.id.in_(select(Piece.session_id)))
                .order_by(ClipSession.id)
            )
        )


def cut_live(db: Session, clips: SessionClips, session: ClipSession, detect: Detector) -> int:
    """Lit les postures des morceaux arrivés (dans l'ordre, sans trou), puis
    coupe chaque combat dont la fin est connue et qui ne l'a pas encore été.
    Quand le dernier morceau est lu, coupe aussi le combat resté ouvert et
    passe la séance à `ready`. Renvoie le nombre de clips coupés."""
    pieces = list(db.scalars(select(Piece).where(Piece.session_id == session.id).order_by(Piece.position)))
    with toutes_saisons(db):
        videos = clips.videos.par_ids(db, [p.video_id for p in pieces if p.video_id is not None])
    frames: list[Frame] = []
    sources: list[tuple[Path, float, float]] = []  # fichier, début dans la séance, durée
    offset, read, ended = 0.0, False, False
    for index, piece in enumerate(pieces):
        video = videos.get(piece.video_id)
        if piece.position != index or video is None or video.statut != "complete":
            break  # un morceau manque encore : on attend
        source = DOSSIER_VIDEOS_LIVE / video.lien_fichier
        poses = _poses_path(session.org_id, piece.id)
        if piece.duration_seconds is None or not poses.exists():
            piece_frames = list(detect(source))
            _save_frames(poses, piece_frames)
            piece.duration_seconds = _duration(source) or (piece_frames[-1].t if piece_frames else 0.0)
            db.commit()
            read = True
        else:
            piece_frames = _load_frames(poses)
        frames += [Frame(t=f.t + offset, people=f.people) for f in piece_frames]
        sources.append((source, offset, piece.duration_seconds))
        offset += piece.duration_seconds
        ended = piece.last
    finished = ended and session.status == "processing"
    if not read and not finished:
        return 0

    done = [x for x in db.scalars(select(Clip.start_seconds).where(Clip.session_id == session.id)) if x is not None]
    folder = dossier_ecole(session.org_id)
    count = 0
    for fight in find_fights(frames):
        if fight.check_reason == REASON_NO_END and not finished:
            continue  # combat encore en cours
        if any(abs(start - fight.start) < 2 for start in done):
            continue
        dest = folder / f"{uuid4().hex}.mp4"
        if not _cut_span(sources, fight.start, fight.end, dest):
            continue
        poster = folder / f"{dest.stem}.jpg"
        number = len(done) + 1
        video = clips.videos.create(
            db,
            ecole_id=session.org_id,
            nom=video_name(session.held_on, session.title, f"combat {number}"),
            lien_fichier=chemin_relatif(session.org_id, dest.name),
            poster=chemin_relatif(session.org_id, poster.name) if generer_poster(dest, poster) else None,
            uploaded_by=session.created_by,
            duree_secondes=duree_secondes(dest),
            compresse=True,
        )
        clips.add_clip(
            db,
            session.id,
            video.id,
            [None] * fight.fighters,
            check_reason=fight.check_reason or REASON_NAMES,
            start_seconds=fight.start,
        )
        done.append(fight.start)
        count += 1
    if finished:
        session.status = "ready"
        db.commit()
    return count


def _cut_span(sources: list[tuple[Path, float, float]], start: float, end: float, dest: Path) -> bool:
    """Un combat peut chevaucher deux morceaux ou plus : ils sont recollés
    (concat de ffmpeg) le temps de la coupe."""
    used = [s for s in sources if s[1] < end and s[1] + s[2] > start]
    if not used:
        return False
    if len(used) == 1:
        source, offset, _ = used[0]
        return cut_clip(source, start - offset, end - offset, dest)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as listing:
        for source, _, _ in used:
            listing.write(f"file '{source}'\n")
    try:
        return _ffmpeg(
            ["-f", "concat", "-safe", "0", "-i", listing.name, "-ss", f"{start - used[0][1]:.2f}"], end - start, dest
        )
    finally:
        Path(listing.name).unlink(missing_ok=True)


def _duration(path: Path) -> float | None:
    try:
        result = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(path)], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    m = _RE_DURATION.search(result.stderr)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else None


def _poses_path(org_id: int, piece_id: int) -> Path:
    """Les postures lues d'un morceau, gardées à côté des vidéos : chaque
    passage relit les combats de toute la séance sans relancer YOLO."""
    return dossier_ecole(org_id) / "sparring-poses" / f"{piece_id}.json"


def _save_frames(path: Path, frames: list[Frame]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [[round(f.t, 3), [[[round(v, 1) for v in k] for k in p.keypoints] for p in f.people]] for f in frames]
    path.write_text(json.dumps(data, separators=(",", ":")))


def _load_frames(path: Path) -> list[Frame]:
    return [Frame(t=t, people=[Pose([tuple(k) for k in p]) for p in people]) for t, people in json.loads(path.read_text())]
