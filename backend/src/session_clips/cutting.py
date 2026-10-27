"""Découpe d'une séance en clips (spec/modules/video-combats.md §5, étape 2),
lancée par le conteneur `sparring-worker` (app/sparring_worker.py).

Pour chaque combat repéré (fights.py), ffmpeg coupe un clip en 720p, le
range dans le module `videos` puis dans la séance (`SessionClips.add_clip`).
Les noms ne sont pas encore reconnus (V3) : chaque clip part dans
« À vérifier ». La vidéo brute est gardée jusqu'à la validation.
"""

from __future__ import annotations

import subprocess
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

from .fights import find_fights
from .models import Clip, ClipSession
from .service import SessionClips, video_name
from .signals import Frame

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
    try:
        result = subprocess.run(
            [
                imageio_ffmpeg.get_ffmpeg_exe(),
                "-y",
                "-ss", f"{start:.2f}",
                "-i", str(source),
                "-t", f"{end - start:.2f}",
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
