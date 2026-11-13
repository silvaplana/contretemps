"""Montre ce que le serveur a vu dans un essai du Labo de Fights, pour
comprendre un signe manqué (Seb, 12/11/2026 : accès en lecture au Labo par
l'action « Maintenance du VPS », DEPLOY.md §6). N'écrit rien.

    python -m app.lire_essai_labo            # les essais de toutes les écoles
    python -m app.lire_essai_labo --essai 4  # le détail d'un essai

Le détail donne la vidéo telle que lue (codec, taille, rotation, images/s),
les signes repérés, les gestes image par image, et les postures gardées
(gzip + base64, entre deux repères) pour rejouer la détection ailleurs.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import subprocess

import imageio_ffmpeg
from sqlalchemy import select

from app import main  # noqa: F401  (toutes les tables connues de SQLAlchemy)
from db import SessionLocal
from saisons.portee import toutes_saisons
from session_clips import lab
from session_clips.cutting import _load_frames
from session_clips.fights import find_signs
from session_clips.models import LabTest
from session_clips.signals import are_shaking_hands, are_touching_fists_up, is_fist_up, is_x, main_pair
from videos import Video
from videos.stockage import DOSSIER_VIDEOS_LIVE


def lister(db, out=print) -> None:
    for t in db.scalars(select(LabTest).order_by(LabTest.org_id, LabTest.id)):
        signs = ", ".join(f"{s['kind']} {s['start']}-{s['end']}" for s in lab.signs_of(t))
        out(f"essai {t.id} · école {t.org_id} · {t.title} · {t.status} · {signs or 'aucun signe'}")


def detail(db, test_id: int, out=print) -> None:
    t = db.get(LabTest, test_id)
    if t is None:
        out("Essai introuvable.")
        return
    out(f"essai {t.id} · école {t.org_id} · {t.title} · {t.status}")
    video = db.get(Video, t.video_id) if t.video_id else None
    if video is not None:
        path = DOSSIER_VIDEOS_LIVE / video.lien_fichier
        out(f"fichier {video.lien_fichier} · {path.stat().st_size if path.exists() else 'absent'} octets")
        info = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(path)], capture_output=True, text=True)
        for line in info.stderr.splitlines():
            if any(k in line for k in ("Duration", "Stream", "rotat", "displaymatrix")):
                out("  " + line.strip())
    out("signes gardés :")
    for s in lab.signs_of(t):
        out(f"  {s['kind']} {s['start']} → {s['end']}")
    poses = lab._poses_path(t)
    if not poses.exists():
        out("Pas de postures gardées.")
        return
    frames = _load_frames(poses)
    out(f"signes recalculés : {[(s.kind, round(s.start, 1), round(s.end, 1)) for s in find_signs(frames)]}")
    out("image par image (t, personnes, poings levés, poings touchés, poignée de main, X) :")
    for f in frames:
        pair = main_pair(f)
        touch = len(pair) == 2 and are_touching_fists_up(*pair)
        shake = len(pair) == 2 and are_shaking_hands(*pair)
        out(
            f"  {f.t:6.2f} n={len(f.people)} poing={sum(is_fist_up(p) for p in f.people)}"
            f" touche={int(touch)} main={int(shake)} x={sum(is_x(p) for p in pair)}"
        )
    out("--- postures (gzip base64) ---")
    out(base64.b64encode(gzip.compress(poses.read_bytes())).decode())
    out("--- fin des postures ---")


def run() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--essai", type=int, help="numéro de l'essai")
    args = parser.parse_args()
    with SessionLocal() as db, toutes_saisons(db):
        if args.essai is None:
            lister(db)
        else:
            detail(db, args.essai)


if __name__ == "__main__":
    run()
