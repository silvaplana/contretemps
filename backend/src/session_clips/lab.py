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
from dataclasses import dataclass
from pathlib import Path

import imageio_ffmpeg
from sqlalchemy import select
from sqlalchemy.orm import Session

from saisons.portee import toutes_saisons
from videos import Video
from videos.stockage import DOSSIER_VIDEOS_LIVE, dossier_ecole

from .fights import SIGNS, SOUNDS, Fight, Sound, find_fights, find_signs, trim
from .framing import FRAMINGS, Box, track, video_size
from .models import ClubSigns, LabTest
from .ports import Member
from .signals import Frame
from .service import ForbiddenError, NotFoundError, SessionClips

THUMB_WIDTH = 160
MAX_SKIP = 10.0  # secondes


# --- Réglages de la découpe du club : signes, cadrage, début et fin ---


@dataclass
class Settings:
    signs: tuple[str, ...] = SIGNS
    framing: str = "wide"
    start_skip: float = 0.0
    end_skip: float = 0.0


def settings(db: Session, org_id: int) -> Settings:
    row = db.get(ClubSigns, org_id)
    if row is None:
        return Settings()
    return Settings(
        signs=tuple(s for s in row.signs.split(",") if s in SIGNS),
        framing=row.framing or "wide",
        start_skip=row.start_skip or 0.0,
        end_skip=row.end_skip or 0.0,
    )


def set_settings(db: Session, member: Member, new: Settings) -> Settings:
    _require_coach(member)
    unknown = set(new.signs) - set(SIGNS)
    if unknown:
        raise ValueError(f"Signe inconnu : {', '.join(sorted(unknown))}")
    if new.framing not in FRAMINGS:
        raise ValueError("Cadrage inconnu")
    if not (0 <= new.start_skip <= MAX_SKIP and 0 <= new.end_skip <= MAX_SKIP):
        raise ValueError(f"Entre 0 et {MAX_SKIP:g} secondes")
    row = db.get(ClubSigns, member.org_id) or ClubSigns(org_id=member.org_id)
    row.signs = ",".join(s for s in SIGNS if s in new.signs)
    row.framing = new.framing
    row.start_skip = new.start_skip
    row.end_skip = new.end_skip
    db.add(row)
    db.commit()
    return settings(db, member.org_id)


def club_fights(
    db: Session, org_id: int, frames: list[Frame], sounds: list[Sound], size: tuple[int, int] | None
) -> list[tuple[Fight, list[Box] | None]]:
    """Les combats selon les réglages du club, chacun avec son cadre (None :
    plan large)."""
    s = settings(db, org_id)
    fights = trim(find_fights(frames, s.signs, sounds), s.start_skip, s.end_skip)
    return [(f, track(frames, f.start, f.end, s.framing, size) if size else None) for f in fights]


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


def rename_test(db: Session, member: Member, test_id: int, title: str) -> LabTest:
    """Le crayon à côté du nom de l'essai (Seb, 12/11)."""
    found = test(db, member, test_id)
    if not title:
        raise ValueError("Donnez un nom à l'essai")
    found.title = title[:150]
    db.commit()
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


def fights_of(db: Session, found: LabTest) -> list[tuple[Fight, list[Box] | None]]:
    """Les combats et leur cadre selon les réglages du club, recalculés à
    chaque fois (sans relire la vidéo)."""
    path = _poses_path(found)
    if found.status != "ready" or not path.exists():
        return []
    from .cutting import _load_frames

    with toutes_saisons(db):
        video = db.get(Video, found.video_id) if found.video_id else None
    size = video_size(DOSSIER_VIDEOS_LIVE / video.lien_fichier) if video is not None else None
    sounds = [(s["kind"], s["start"]) for s in signs_of(found) if s["kind"] in SOUNDS]
    return club_fights(db, found.org_id, _load_frames(path), sounds, size)


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


def read_test(db: Session, clips: SessionClips, found: LabTest, detect, hear=lambda _path: []) -> int:
    """Lit les postures et écoute les sons, repère les signes avec une image
    de chacun, et passe l'essai à `ready`. Renvoie le nombre de signes."""
    from .cutting import _save_frames

    with toutes_saisons(db):
        video = clips.videos.get(db, found.video_id)
    source = DOSSIER_VIDEOS_LIVE / video.lien_fichier
    frames = list(detect(source))
    _save_frames(_poses_path(found), frames)
    signs = [
        {"kind": s.kind, "start": round(s.start, 1), "end": round(s.end, 1), "thumb": thumbnail(source, s.start)}
        for s in find_signs(frames, hear(source))
    ]
    found.signs = json.dumps(signs)
    found.status = "ready"
    db.commit()
    return len(signs)


def reread_test(db: Session, clips: SessionClips, member: Member, test_id: int) -> None:
    """« Relancer la découpe » (Seb, 12/11) : relit les signes sur les postures
    gardées, avec les règles du jour, sans relire la vidéo. Les « Time ! »
    entendus et les images des signes déjà vus sont gardés."""
    from .cutting import _load_frames

    found = test(db, member, test_id)
    path = _poses_path(found)
    if found.status != "ready" or not path.exists():
        return
    before = signs_of(found)
    thumbs = {(s["kind"], s["start"]): s["thumb"] for s in before}
    sounds = [(s["kind"], s["start"]) for s in before if s["kind"] in SOUNDS]
    with toutes_saisons(db):
        video = clips.videos.get(db, found.video_id)
    source = DOSSIER_VIDEOS_LIVE / video.lien_fichier
    signs = []
    for s in find_signs(_load_frames(path), sounds):
        start = round(s.start, 1)
        thumb = thumbs.get((s.kind, start)) or thumbnail(source, s.start)
        signs.append({"kind": s.kind, "start": start, "end": round(s.end, 1), "thumb": thumb})
    found.signs = json.dumps(signs)
    db.commit()


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
