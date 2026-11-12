"""Cadrage d'un clip (spec/modules/video-combats.md §5, Seb 12/11/2026) :
la salle est filmée en plan large ; un clip peut se resserrer sur les deux
combattants, avec plus ou moins de marge (« Moyen » ou « Serré »).

Le cadre garde une taille fixe pendant tout le combat (pas de zoom qui
pompe) et suit le centre des deux plus grands corps (ceux qui ont fait les
signes), lissé sur 2 s pour bouger en douceur. Il est rendu comme une suite
de positions toutes les 0,2 s, relatives à la vidéo (0 à 1) : ffmpeg coupe
avec (cutting.py), et le Labo montre le même cadre sur la vidéo d'origine.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import imageio_ffmpeg

from .signals import Frame, main_pair

FRAMINGS = ("wide", "medium", "tight")
# Marge autour des deux corps, en part de la hauteur de leur boîte.
MARGIN = {"medium": 0.6, "tight": 0.2}
SMOOTH = 2.0  # secondes
STEP = 0.2  # secondes entre deux positions du cadre
MIN_CONFIDENCE = 0.3

Box = tuple[float, float, float, float, float]  # t, x, y, w, h (0 à 1, t depuis le début du clip)


def track(frames: list[Frame], start: float, end: float, framing: str, size: tuple[int, int]) -> list[Box] | None:
    """Le cadre du clip [start, end], ou None pour le plan large (ou si
    personne n'est vu)."""
    if framing not in MARGIN:
        return None
    width, height = size
    seen = []  # t, centre x, centre y, hauteur de cadre nécessaire (px)
    for f in frames:
        if not start <= f.t <= end:
            continue
        points = [(x, y) for p in main_pair(f) for x, y, c in p.keypoints if c >= MIN_CONFIDENCE]
        if not points:
            continue
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        box_w, box_h = max(xs) - min(xs), max(ys) - min(ys)
        pad = MARGIN[framing] * box_h
        need = max(box_h + 2 * pad, (box_w + 2 * pad) * height / width)
        seen.append((f.t, (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, need))
    if not seen:
        return None
    needs = sorted(s[3] for s in seen)
    crop_h = min(height, needs[int(0.9 * (len(needs) - 1))])  # assez grand 9 fois sur 10
    crop_w = crop_h * width / height
    out: list[Box] = []
    t = start
    while t <= end + 1e-6:
        near = [s for s in seen if abs(s[0] - t) <= SMOOTH / 2] or [min(seen, key=lambda s: abs(s[0] - t))]
        cx = sum(s[1] for s in near) / len(near)
        cy = sum(s[2] for s in near) / len(near)
        x = min(max(cx - crop_w / 2, 0), width - crop_w)
        y = min(max(cy - crop_h / 2, 0), height - crop_h)
        out.append((round(t - start, 2), round(x / width, 4), round(y / height, 4), round(crop_w / width, 4), round(crop_h / height, 4)))
        t += STEP
    return out


def ffmpeg_filter(boxes: list[Box], size: tuple[int, int], commands: Path) -> str:
    """Le filtre ffmpeg qui suit le cadre : taille fixe, position changée
    toutes les 0,2 s (fichier de commandes `sendcmd`)."""
    width, height = size
    w = int(boxes[0][3] * width) // 2 * 2
    h = int(boxes[0][4] * height) // 2 * 2
    commands.write_text(
        "".join(f"{t:.2f} crop x {int(x * width)}, crop y {int(y * height)};\n" for t, x, y, _, _ in boxes)
    )
    return f"sendcmd=f='{commands}',crop={w}:{h}:{int(boxes[0][1] * width)}:{int(boxes[0][2] * height)}"


_RE_SIZE = re.compile(r"Video:.*?(\d{2,5})x(\d{2,5})")
_RE_ROTATION = re.compile(r"rotation of (-?\d+(?:\.\d+)?)|rotate\s*:\s*(-?\d+)")


def video_size(path: Path) -> tuple[int, int] | None:
    """Largeur et hauteur de l'image telle qu'affichée (vidéo de téléphone
    tournée comprise), comme la lisent YOLO et ffmpeg."""
    try:
        result = subprocess.run(
            [imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(path)], capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return None
    m = _RE_SIZE.search(result.stderr)
    if not m:
        return None
    width, height = int(m[1]), int(m[2])
    r = _RE_ROTATION.search(result.stderr)
    if r and abs(round(float(r[1] or r[2]))) % 180 == 90:
        width, height = height, width
    return width, height
