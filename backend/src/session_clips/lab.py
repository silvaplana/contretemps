"""Le Labo de Fights (spec/modules/video-combats.md §6.5 bis) : un coach envoie
une vidéo déjà filmée et voit ce que la découpe y repère (les signes, une
petite image de chacun, les combats), sans filmer ni rien ranger dans
« Mes combats ». Et les « Signes et sons du club », que la découpe prend.

La lecture (YOLO) est faite par le worker (app/sparring_worker.py), à toute
heure : un essai est court. Les postures sont gardées sur disque, à côté de
celles des morceaux de la caméra : changer les signes cochés recalcule les
combats sans relire la vidéo.
"""

from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path

import imageio_ffmpeg
from sqlalchemy import select
from sqlalchemy.orm import Session

from saisons.portee import toutes_saisons
from videos import Video
from videos.stockage import DOSSIER_VIDEOS_LIVE, dossier_ecole

from .fights import SIGNS, Fight, find_fights, find_signs
from .models import ClubSigns, LabTest
from .ports import Member
from .service import ForbiddenError, NotFoundError, SessionClips

THUMB_WIDTH = 160


# --- Signes et sons du club ---


def enabled_signs(db: Session, org_id: int) -> tuple[str, ...]:
    row = db.get(ClubSigns, org_id)
    return SIGNS if row is None else tuple(s for s in row.signs.split(",") if s in SIGNS)


def set_signs(db: Session, member: Member, signs: list[str]) -> tuple[str, ...]:
    _require_coach(member)
    unknown = set(signs) - set(SIGNS)
    if unknown:
        raise ValueError(f"Signe inconnu : {', '.join(sorted(unknown))}")
    row = db.get(ClubSigns, member.org_id) or ClubSigns(org_id=member.org_id)
    row.signs = ",".join(s for s in SIGNS if s in signs)
    db.add(row)
    db.commit()
    return enabled_signs(db, member.org_id)


# --- Essais ---


def tests(db: Session, member: Member) -> list[LabTest]:
    _require_coach(member)
    return list(
        db.scalars(select(LabTest).where(LabTest.org_id == member.org_id).order_by(LabTest.id.desc()))
    )


def test(db: Session, member: Member, test_id: int) -> LabTest:
    _require_coach(member)
    found = db.get(LabTest, test_id)
    if found is None or found.org_id != member.org_id:
        raise NotFoundError("Essai introuvable")
    return found


def create_test(db: Session, clips: SessionClips, member: Member, upload_id: str, title: str) -> LabTest:
    """« Importer une vidéo » : la vidéo arrive par l'envoi par blocs du
    module Vidéos, gardée telle quelle (pas compressée)."""
    _require_coach(member)
    upload = clips.videos.obtenir_televersement(db, upload_id)
    if upload is None or upload.ecole_id != member.org_id:
        raise NotFoundError("Envoi introuvable")
    video = clips.videos.finaliser(
        db, upload_id, nom=f"Labo · {title}", uploaded_by=member.person_id, deja_compresse=True
    )
    found = db.scalar(select(LabTest).where(LabTest.video_id == video.id))
    if found is None:  # sinon, double clic
        found = LabTest(org_id=member.org_id, title=title, video_id=video.id, created_by=member.person_id)
        db.add(found)
        db.commit()
        db.refresh(found)
    return found


def delete_test(db: Session, clips: SessionClips, member: Member, test_id: int) -> None:
    found = test(db, member, test_id)
    _poses_path(found).unlink(missing_ok=True)
    if found.video_id is not None:
        with toutes_saisons(db):
            clips.videos.delete(db, found.video_id)  # efface aussi l'essai (_video_deleted)
    if db.get(LabTest, test_id) is not None:
        db.delete(found)
        db.commit()


def signs_of(found: LabTest) -> list[dict]:
    return json.loads(found.signs) if found.signs else []


def fights_of(db: Session, found: LabTest) -> list[Fight]:
    """Les combats avec les signes cochés du club, recalculés à chaque fois."""
    path = _poses_path(found)
    if found.status != "ready" or not path.exists():
        return []
    from .cutting import _load_frames

    return find_fights(_load_frames(path), enabled_signs(db, found.org_id))


# --- Lecture par le worker ---


def tests_to_read(db: Session) -> list[LabTest]:
    with toutes_saisons(db):
        return list(
            db.scalars(
                select(LabTest)
                .join(Video, Video.id == LabTest.video_id)
                .where(LabTest.status == "processing", Video.statut == "complete")
                .order_by(LabTest.id)
            )
        )


def read_test(db: Session, clips: SessionClips, found: LabTest, detect) -> int:
    """Lit les postures, repère les signes avec une image de chacun, et
    passe l'essai à `ready`. Renvoie le nombre de signes."""
    from .cutting import _save_frames

    with toutes_saisons(db):
        video = clips.videos.get(db, found.video_id)
    source = DOSSIER_VIDEOS_LIVE / video.lien_fichier
    frames = list(detect(source))
    _save_frames(_poses_path(found), frames)
    signs = [
        {"kind": s.kind, "start": round(s.start, 1), "end": round(s.end, 1), "thumb": thumbnail(source, s.start)}
        for s in find_signs(frames)
    ]
    found.signs = json.dumps(signs)
    found.status = "ready"
    db.commit()
    return len(signs)


def thumbnail(source: Path, t: float) -> str | None:
    """L'image de la vidéo au moment du signe, petite (jpeg en data URL :
    quelques ko, gardée avec l'essai)."""
    try:
        result = subprocess.run(
            [
                imageio_ffmpeg.get_ffmpeg_exe(),
                "-ss", f"{t:.2f}",
                "-i", str(source),
                "-frames:v", "1",
                "-vf", f"scale={THUMB_WIDTH}:-2",
                "-f", "image2pipe",
                "-c:v", "mjpeg",
                "-q:v", "6",
                "-",
            ],
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0 or not result.stdout:
        return None
    return "data:image/jpeg;base64," + base64.b64encode(result.stdout).decode()


def _poses_path(found: LabTest) -> Path:
    return dossier_ecole(found.org_id) / "sparring-poses" / f"lab-{found.id}.json"


def _require_coach(member: Member) -> None:
    if not member.is_coach:
        raise ForbiddenError("Réservé aux coachs")
