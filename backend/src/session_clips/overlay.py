"""Incrustation dans le combat archivé du Timer étendu (spec/modules/
video-combats.md §6.5 quater, maquette validée par Seb le 21/11/2026).

Au choix dans Paramètres du Timer : les noms au début (ils arrivent chacun de
leur côté, se cognent au milieu, puis restent en haut), le chrono en chiffres
rouges (« R1, R2… » seulement s'il y a plusieurs rounds), le vainqueur à la
fin et une musique choisie à « Archiver ». Au gong la vidéo s'arrête sur sa
dernière image ; une fois le gong fini, George annonce le vainqueur et le
bandeau monte quand il dit le nom.

Tout se fait en une seule compression, à la place de celle du module Vidéos
(Seb, 15/10 : jamais deux) : les images à incruster sont dessinées ici
(Pillow), une par changement, puis ffmpeg les pose sur la vidéo et mélange
les sons. Tâche de fond (app/video_compression_worker.py) : personne
n'attend devant.
"""

from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from sqlalchemy import select
from sqlalchemy.orm import Session

from videos.stockage import DOSSIER_VIDEOS_LIVE

from . import announcer
from .framing import video_size
from .models import Clip, ClipSession

ASSETS = Path(__file__).parent / "overlay_assets"
SOUNDS = Path(__file__).parent / "timer_sounds"
MUSICS = ("montage", "entree", "rock")
FPS = 25
MAX_HEIGHT = 1080  # comme la compression du module Vidéos
CRF = 28

# Les temps de la maquette (secondes).
ARRIVAL, SHAKE_END, MOVE_START, MOVE_END = 0.55, 1.05, 1.8, 2.4
GONG_GAP = 3.0  # la voix part une fois le gong fini
NAME_GAP = 0.7  # entre « And the winner… » et le nom, comme au Timer

YELLOW = (245, 233, 74)
RED = (255, 45, 32)


# --- La demande, gardée sur le clip ---------------------------------------


def wanted(overlay: dict | None) -> bool:
    """Y a-t-il quelque chose à incruster ?"""
    return bool(overlay) and any(overlay.get(k) for k in ("names", "winner", "chrono", "music"))


def pending(db: Session) -> list[Clip]:
    return list(db.scalars(select(Clip).where(Clip.overlay.is_not(None)).order_by(Clip.id)))


def render_pending(db: Session, videos) -> int:
    """Les combats archivés qui attendent leur incrustation, une fois leur
    vidéo arrivée en entier. Un échec rend la vidéo à la compression
    ordinaire : elle reste visible, sans incrustation."""
    done = 0
    for clip in pending(db):
        video = videos.get(db, clip.video_id)
        if video is None:
            clip.overlay = None
            db.commit()
            continue
        if video.statut != "complete" or not video.lien_fichier:
            continue
        org_id = db.get(ClipSession, clip.session_id).org_id
        source = DOSSIER_VIDEOS_LIVE / video.lien_fichier
        # « -i » : incrustée (le diagnostic du serveur le montre).
        target = source.with_name(f"{source.stem}-i.mp4")
        ok = False
        try:
            ok = render(source, target, clip.overlay, org_id)
        except Exception:  # noqa: BLE001 — jamais bloquer le worker
            ok = False
        clip.overlay = None
        if ok:
            video.duree_secondes = round(seconds(target))  # le vainqueur ajoute quelques secondes
            videos.remplacer_fichier(db, video, target)
            done += 1
        else:
            target.unlink(missing_ok=True)
            video.compresse = False  # la compression ordinaire la reprend
            db.commit()
    return done


# --- Le plan dans le temps --------------------------------------------------


_RE_DURATION = re.compile(r"Duration:\s*(\d+):(\d{2}):(\d{2}(?:\.\d+)?)")


def seconds(path: Path) -> float:
    """Durée d'un fichier son ou vidéo. Les vidéos du navigateur (webm) n'en
    disent souvent rien : on les lit alors en entier."""
    out = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(path)], capture_output=True, text=True, timeout=30)
    m = _RE_DURATION.search(out.stderr)
    if m:
        return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
    return imageio_ffmpeg.count_frames_and_secs(str(path))[1]


def has_audio(path: Path) -> bool:
    out = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(path)], capture_output=True, text=True, timeout=30)
    return "Audio:" in out.stderr


def timeline(overlay: dict, duration: float, name_voice: Path | None) -> dict:
    """Quand se passe quoi, en secondes dans la vidéo finale.

    `end` : fin du combat (le gong) ; `banner` : le bandeau du résultat
    monte ; `total` : fin de la vidéo ; `sounds` : (fichier, début)."""
    result = overlay.get("result")  # 0, 1, "draw" ou None
    plan = {"end": duration, "banner": None, "total": duration, "sounds": []}
    show = result is not None and overlay.get("winner")
    speak = result is not None and overlay.get("announce")
    if not (show or speak):
        return plan
    gong = SOUNDS / "cloche-fin-de-round.mp3"
    plan["sounds"].append((gong, duration))
    voice = duration + GONG_GAP
    end = voice + 4.0
    banner = voice
    if speak and result == "draw":
        nul = SOUNDS / "annonce-nul.mp3"
        plan["sounds"].append((nul, voice))
        end = voice + seconds(nul) + 1.5
    elif speak:
        intro = SOUNDS / "annonce-vainqueur.mp3"
        plan["sounds"].append((intro, voice))
        name = name_voice or SOUNDS / ("annonce-droite.mp3" if result else "annonce-gauche.mp3")
        banner = voice + seconds(intro) + NAME_GAP
        name_length = seconds(name)
        plan["sounds"].append((name, banner))
        crowd = SOUNDS / "foule.mp3"
        plan["sounds"].append((crowd, banner + 0.55 * name_length))
        end = max(banner + name_length, banner + 0.55 * name_length + seconds(crowd)) + 1.0
    plan["banner"] = banner if show else None
    plan["total"] = end
    return plan


def chrono_at(overlay: dict, t: float) -> tuple[str, str] | None:
    """(étiquette, temps) du chrono à l'instant t de la vidéo, comme le Timer
    l'affichait : « R2 », « Repos » ou rien en un seul round."""
    phases = sorted(overlay.get("phases") or [], key=lambda p: p["t"])
    if not phases:
        return None
    current = phases[0]
    for p in phases:
        if p["t"] <= t:
            current = p
    left = max(0, math.ceil(current["total"] - max(0.0, t - current["t"]) - 1e-6))
    label = "" if (overlay.get("rounds") or 1) <= 1 else ("REPOS" if current["n"] == 0 else f"R{current['n']}")
    return label, f"{left // 60}:{left % 60:02d}"


# --- Les dessins ------------------------------------------------------------


@lru_cache(maxsize=16)
def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(ASSETS / "Inter-Black.otf"), size)


def _gradient(width: int, height: int, stops: list[tuple[float, tuple[int, int, int]]], vertical=False) -> Image.Image:
    n = height if vertical else width
    line = Image.new("RGB", (n, 1))
    for i in range(n):
        x = i / max(1, n - 1)
        for (a, ca), (b, cb) in zip(stops, stops[1:]):
            if a <= x <= b:
                k = (x - a) / (b - a) if b > a else 0
                line.putpixel((i, 0), tuple(round(ca[j] + (cb[j] - ca[j]) * k) for j in range(3)))
                break
    if vertical:
        return line.rotate(-90, expand=True).resize((width, height))
    return line.resize((width, height))


def _mask(size, draw_shape, scale=4) -> Image.Image:
    """Un masque lissé : dessiné en grand puis réduit."""
    big = Image.new("L", (size[0] * scale, size[1] * scale), 0)
    draw_shape(ImageDraw.Draw(big), scale)
    return big.resize(size, Image.LANCZOS)


def _text(img: Image.Image, xy, text: str, size: int, fill, shadow=True, anchor="lm", spacing=0):
    draw = ImageDraw.Draw(img)
    if shadow:
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((xy[0], xy[1] + size * 0.07), text, font=font(size), fill=(0, 0, 0, 170), anchor=anchor)
        img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(size * 0.12)))
    if spacing:
        x = xy[0]
        for c in text:
            draw.text((x, xy[1]), c, font=font(size), fill=fill, anchor=anchor)
            x += draw.textlength(c, font=font(size)) + spacing
    else:
        draw.text(xy, text, font=font(size), fill=fill, anchor=anchor)


def plate(name: str, side: int, u: float) -> Image.Image:
    """Le nom d'un combattant : rouge à gauche, bleu à droite, coupé en biais
    du côté du milieu."""
    h, size = round(9 * u), round(4.4 * u)
    text = name.upper()
    width = round(3 * u + font(size).getlength(text) + 5 * u)
    if side == 0:
        fill = _gradient(width, h, [(0, (94, 9, 5)), (0.7, (212, 39, 27)), (1, (255, 90, 69))])
        poly = [(0, 0), (width, 0), (width * 0.92, h), (0, h)]
        x = 3 * u
    else:
        fill = _gradient(width, h, [(0, (79, 141, 255)), (0.3, (29, 95, 208)), (1, (6, 33, 79))])
        poly = [(width * 0.08, 0), (width, 0), (width, h), (0, h)]
        x = 5 * u
    mask = _mask((width, h), lambda d, s: d.polygon([(px * s, py * s) for px, py in poly], fill=255))
    img = Image.new("RGBA", (width, h), (0, 0, 0, 0))
    img.paste(fill, (0, 0), mask)
    _text(img, (x, h / 2), text, size, (255, 255, 255))
    return img


def glow(img: Image.Image, color, radius: float) -> Image.Image:
    """L'image entourée d'une lueur (le vainqueur, le VS, les chiffres)."""
    pad = round(radius * 2)
    out = Image.new("RGBA", (img.width + 2 * pad, img.height + 2 * pad), (0, 0, 0, 0))
    halo = Image.new("RGBA", out.size, color + (0,))
    alpha = Image.new("L", out.size, 0)
    alpha.paste(img.getchannel("A"), (pad, pad))
    halo.putalpha(alpha.filter(ImageFilter.GaussianBlur(radius)).point(lambda a: min(255, a * 2)))
    out.alpha_composite(halo)
    out.alpha_composite(img, (pad, pad))
    return out


def dim(img: Image.Image) -> Image.Image:
    """Le perdant s'éteint."""
    r, g, b, a = img.split()
    grey = Image.merge("RGB", (r, g, b)).convert("L").point(lambda v: v * 0.6)
    return Image.merge("RGBA", (grey, grey, grey, a))


def vs_badge(u: float) -> Image.Image:
    d = round(8 * u)
    ball = Image.new("RGBA", (d, d), (0, 0, 0, 0))
    steps = 24
    for i in range(steps):
        k = i / (steps - 1)
        r = d / 2 * (1 - k)
        c = tuple(round(a + (b - a) * k) for a, b in zip((184, 154, 0), (255, 251, 208)))
        cx, cy = d / 2 - k * d * 0.15, d / 2 - k * d * 0.2
        ImageDraw.Draw(ball).ellipse((cx - r, cy - r, cx + r, cy + r), fill=c + (255,))
    mask = _mask((d, d), lambda dr, s: dr.ellipse((0, 0, d * s - 1, d * s - 1), fill=255))
    ball.putalpha(mask)
    text = Image.new("RGBA", (d, d), (0, 0, 0, 0))
    ImageDraw.Draw(text).text((d / 2, d / 2), "VS", font=font(round(3.4 * u)), fill=(21, 22, 26), anchor="mm")
    text = text.transform(text.size, Image.AFFINE, (1, 0.2, -0.1 * d, 0, 1, 0), Image.BICUBIC)
    ball.alpha_composite(text)
    return glow(ball, YELLOW, 1.2 * u)


def burst(u: float) -> Image.Image:
    d = round(40 * u)
    img = Image.new("RGBA", (d, d), (0, 0, 0, 0))
    stops = [(0, (255, 255, 255, 255)), (0.18, (255, 240, 150, 230)), (0.45, (255, 120, 40, 90)), (0.7, (255, 120, 40, 0))]
    draw = ImageDraw.Draw(img)
    for i in range(60, 0, -1):
        x = i / 60
        for (a, ca), (b, cb) in zip(stops, stops[1:]):
            if a <= x <= b:
                k = (x - a) / (b - a)
                c = tuple(round(ca[j] + (cb[j] - ca[j]) * k) for j in range(4))
                break
        else:
            c = (0, 0, 0, 0)
        r = d / 2 * x
        draw.ellipse((d / 2 - r, d / 2 - r, d / 2 + r, d / 2 + r), fill=c)
    return img.filter(ImageFilter.GaussianBlur(u))


# Les chiffres à segments du Timer (Timer.jsx, Afficheur), même dessin.
def _hseg(y):
    return [(9, y), (14, y - 5), (46, y - 5), (51, y), (46, y + 5), (14, y + 5)]


def _vseg(x, y):
    return [(x, y), (x + 5, y + 5), (x + 5, y + 37), (x, y + 42), (x - 5, y + 37), (x - 5, y + 5)]


SEGMENTS = {"a": _hseg(6), "g": _hseg(54), "d": _hseg(102), "f": _vseg(6, 9), "b": _vseg(54, 9), "e": _vseg(6, 57), "c": _vseg(54, 57)}
ON = ["abcdef", "bc", "abged", "abgcd", "fgbc", "afgcd", "afgedc", "abc", "abcdefg", "abcdfg"]


def chrono(label: str, time: str, u: float) -> Image.Image:
    """« R1 » en jaune puis le temps en chiffres rouges, sans fond (Seb, 21/11)."""
    h = 5.6 * u
    k = h / 108
    gap = 0.5 * u
    widths = [(24 if c == ":" else 60) * k for c in time]
    digits_w = sum(widths) + gap * (len(time) - 1)
    label_size = round(3.2 * u)
    label_w = font(label_size).getlength(label) + 1.2 * u if label else 0
    width, height = round(digits_w + 2 * u), round(h + 2 * u)
    s = 4
    big = Image.new("RGBA", (width * s, height * s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(big)
    x = u * s
    top = u * s
    for c, w in zip(time, widths):
        if c == ":":
            for y in (27, 70):
                draw.rounded_rectangle(((x + 7 * k * s), top + y * k * s, x + 18 * k * s, top + (y + 11) * k * s), radius=2 * k * s, fill=RED + (255,))
        else:
            for name, pts in SEGMENTS.items():
                on = name in ON[int(c)]
                draw.polygon([(x + px * k * s, top + py * k * s) for px, py in pts], fill=RED + ((255,) if on else (26,)))
        x += (w + gap) * s
    digits = big.resize((width, height), Image.LANCZOS)
    # Penchés comme au Timer (skewX -5°).
    digits = digits.transform(digits.size, Image.AFFINE, (1, math.tan(math.radians(5)), -height * 0.04, 0, 1, 0), Image.BICUBIC)
    digits = glow(digits, RED, 0.6 * u)
    if not label:
        return digits
    img = Image.new("RGBA", (round(label_w) + digits.width, digits.height), (0, 0, 0, 0))
    _text(img, (round(u), img.height / 2), label, label_size, YELLOW)
    img.alpha_composite(digits, (round(label_w), 0))
    return img


def banner(result, names: list[str], u: float) -> Image.Image:
    """Le bandeau du résultat : poing levé et nom du vainqueur, ou match nul."""
    small, large = round(2.4 * u), round(5.4 * u)
    if result == "draw":
        title, label = "MATCH NUL", ""
    else:
        title, label = names[result].upper(), "VAINQUEUR"
    icon_w = round(7 * u)
    text_w = max(font(large).getlength(title), font(small).getlength(label) + len(label) * 0.5 * u)
    width, height = round(2 * u + icon_w + 2 * u + text_w + 4 * u), round(12.5 * u)
    radius, border = 2 * u, max(2, round(0.3 * u))
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    fill = _gradient(width, height, [(0, (30, 26, 8)), (1, (12, 12, 14))], vertical=True)
    mask = _mask((width, height), lambda d, s: d.rounded_rectangle((0, 0, width * s - 1, height * s - 1), radius * s, fill=235))
    img.paste(fill, (0, 0), mask)
    ring = _mask(
        (width, height),
        lambda d, s: d.rounded_rectangle((0, 0, width * s - 1, height * s - 1), radius * s, outline=255, width=border * s),
    )
    img.paste(Image.new("RGBA", (width, height), YELLOW + (255,)), (0, 0), ring)
    if result == "draw":
        bar_h = round(1.2 * u)
        d = ImageDraw.Draw(img)
        for y in (height / 2 - 1.8 * u, height / 2 + 0.6 * u):
            d.rounded_rectangle((2 * u, y, 2 * u + icon_w, y + bar_h), radius=bar_h / 2, fill=YELLOW + (255,))
        _text(img, (4 * u + icon_w, height / 2), title, large, (255, 255, 255))
    else:
        fist = Image.open(ASSETS / "poing.png").convert("RGBA")
        fist = fist.resize((icon_w, round(icon_w * fist.height / fist.width)), Image.LANCZOS)
        img.alpha_composite(fist, (round(2 * u), round((height - fist.height) / 2)))
        _text(img, (4 * u + icon_w, height / 2 - 2.6 * u), label, small, YELLOW, shadow=False, spacing=0.5 * u)
        _text(img, (4 * u + icon_w, height / 2 + 1.2 * u), title, large, (255, 255, 255))
    return glow(img, YELLOW, 2 * u)


# --- Image par image ------------------------------------------------------------


def _ease_in(x):
    return x * x * x


def _ease_in_out(x):
    return 4 * x**3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def _clamp(x):
    return max(0.0, min(1.0, x))


def _pop(x):
    if x <= 0:
        return 0.0
    return 1.35 * _ease_in_out(x / 0.6) if x < 0.6 else 1.35 - 0.35 * _clamp((x - 0.6) / 0.4)


class Frames:
    """Dessine les images à incruster, à la taille de la vidéo."""

    def __init__(self, overlay: dict, plan: dict, width: int, height: int):
        self.o, self.plan, self.w, self.h = overlay, plan, width, height
        u = self.u = width / 100
        names = overlay.get("labels") or ["", ""]
        self.names = [n or "Inconnu" for n in names]
        self.show_names = bool(overlay.get("names"))
        if self.show_names:
            self.plates = [plate(self.names[i], i, u) for i in (0, 1)]
            self.vs = vs_badge(u)
            self.burst = burst(u)
        result = overlay.get("result")
        if plan["banner"] is not None:
            self.banner = banner(result, self.names, u)
            if self.show_names and result in (0, 1):
                self.final_plates = [glow(p, YELLOW, 1.5 * u) if i == result else dim(p) for i, p in enumerate(self.plates)]
        self.chronos = {}

    def key(self, t: float):
        """Ce qui change d'une image à l'autre : deux instants de même clé
        donnent la même image."""
        names = None
        if self.show_names:
            names = round(t * FPS) if t < MOVE_END else "top"
            if self.plan["banner"] is not None and t >= self.plan["banner"] and names == "top":
                names = "final"
        clock = chrono_at(self.o, min(t, self.plan["end"] - 1e-3)) if self.o.get("chrono") else None
        band = None
        if self.plan["banner"] is not None and t >= self.plan["banner"]:
            band = min(round((t - self.plan["banner"]) * FPS), round(0.5 * FPS))
        dark = t >= self.plan["end"] + 1.0
        return names, clock, band, dark

    def draw(self, t: float) -> Image.Image:
        names, clock, band, dark = self.key(t)
        u = self.u
        img = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 120) if dark else (0, 0, 0, 0))
        if names is not None:
            self._names(img, min(t, MOVE_END) if names in ("top", "final") else t, names == "final")
        if clock:
            pic = self.chronos.get(clock)
            if pic is None:
                pic = self.chronos[clock] = chrono(*clock, u)
            img.alpha_composite(pic, (round(self.w - pic.width - 1.4 * u), round(1.4 * u)))
        if band is not None:
            v = _ease_in_out(_clamp(band / (0.5 * FPS)))
            s = 0.8 + 0.2 * v
            pic = self.banner.resize((max(1, round(self.banner.width * s)), max(1, round(self.banner.height * s))), Image.LANCZOS)
            y = self.h - 6 * u - pic.height + (1 - v) * 30 * u + self.banner.height * (1 - s) / 2
            img.alpha_composite(pic, (round((self.w - pic.width) / 2), round(y)))
        return img

    def _names(self, img: Image.Image, t: float, final: bool):
        u, w, h = self.u, self.w, self.h
        a = _ease_in(_clamp(t / ARRIVAL))
        shake = 0.0
        if ARRIVAL < t < SHAKE_END:
            shake = math.sin((t - ARRIVAL) * 70) * 1.4 * (1 - (t - ARRIVAL) / (SHAKE_END - ARRIVAL))
        m = _ease_in_out(_clamp((t - MOVE_START) / (MOVE_END - MOVE_START)))
        y = h * (0.5 - 0.41 * m)
        s = 1 - 0.45 * m
        gap = 4.6 * _ease_in_out(_clamp((t - 0.6) / 0.3))
        if ARRIVAL <= t < ARRIVAL + 0.45:
            c = _clamp((t - ARRIVAL) / 0.45)
            b = self.burst.resize([max(1, round(self.burst.width * (0.2 + 1.1 * math.sqrt(c))))] * 2, Image.BILINEAR)
            b.putalpha(b.getchannel("A").point(lambda v: round(v * (1 - c))))
            img.alpha_composite(b, (round(w / 2 - b.width / 2), round(h / 2 - b.height / 2)))
        plates = self.final_plates if final and hasattr(self, "final_plates") else self.plates
        for i, sens in ((0, -1), (1, 1)):
            p = plates[i]
            base = self.plates[i]
            extra = (p.width - base.width) / 2  # la lueur du vainqueur déborde
            pw, ph = max(1, round(p.width * s)), max(1, round(p.height * s))
            pic = p.resize((pw, ph), Image.LANCZOS) if s != 1 else p
            dx = sens * ((1 - a) * 75 + gap * s) * u + shake * u
            inner = w / 2 + dx  # le bord côté milieu
            x = inner - pw + extra * s if sens < 0 else inner - extra * s
            img.alpha_composite(pic, (round(x), round(y - ph / 2)))
        scale = _pop((t - ARRIVAL) / 0.5) * s
        if scale > 0.01:
            vs = self.vs.resize([max(1, round(self.vs.width * scale))] * 2, Image.LANCZOS)
            img.alpha_composite(vs, (round(w / 2 + shake * u - vs.width / 2), round(y - vs.height / 2)))


# --- ffmpeg -----------------------------------------------------------------------


def render(source: Path, target: Path, overlay: dict, org_id: int) -> bool:
    """Fabrique la vidéo incrustée et compressée. `False` si ffmpeg échoue."""
    size = video_size(source)
    if size is None:
        return False
    height = min(MAX_HEIGHT, size[1]) // 2 * 2
    width = round(size[0] * height / size[1] / 2) * 2
    duration = seconds(source)
    name_voice = None
    result = overlay.get("result")
    if overlay.get("announce") and result in (0, 1):
        person, full = (overlay.get("people") or [None, None])[result], (overlay.get("voices") or [None, None])[result]
        if person and full:
            try:
                name_voice = announcer.name_file(org_id, person, full)
            except Exception:  # noqa: BLE001 — sans la voix du nom : « le coin gauche/droit »
                name_voice = None
    plan = timeline(overlay, duration, name_voice)
    work = Path(tempfile.mkdtemp(prefix="incrustation-", dir=target.parent))
    try:
        frames = Frames(overlay, plan, width, height)
        made: dict = {}
        count = math.ceil(plan["total"] * FPS)
        for i in range(count):
            t = i / FPS
            k = frames.key(t)
            if k not in made:
                made[k] = work / f"u{len(made)}.png"
                frames.draw(t).save(made[k], compress_level=1)
            os.link(made[k], work / f"f{i:06d}.png")
        return _ffmpeg(source, target, work, overlay, plan, width, height, duration)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _ffmpeg(source, target, work, overlay, plan, width, height, duration) -> bool:
    total, end = plan["total"], plan["end"]
    args = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(source),
            "-framerate", str(FPS), "-i", str(work / "f%06d.png")]
    tail = max(0.0, total - duration)
    video = (f"[0:v]scale={width}:{height},setsar=1,fps={FPS},tpad=stop_mode=clone:stop_duration={tail:.3f}[base];"
             "[base][1:v]overlay=0:0:eof_action=pass,format=yuv420p[v]")
    audio, mix, n = [], [], 2
    if has_audio(source):
        audio.append("[0:a]aresample=44100,apad[a0]")
    else:
        args += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        audio.append(f"[{n}:a]anull[a0]")
        n += 1
    mix.append("[a0]")
    for path, start in plan["sounds"]:
        args += ["-i", str(path)]
        ms = round(start * 1000)
        audio.append(f"[{n}:a]aresample=44100,adelay={ms}:all=1[s{n}]")
        mix.append(f"[s{n}]")
        n += 1
    music = overlay.get("music")
    if music in MUSICS:
        args += ["-stream_loop", "-1", "-i", str(SOUNDS / f"musique-{music}.mp3")]
        fade = max(0.0, total - 1.2)
        audio.append(
            f"[{n}:a]aresample=44100,volume='if(lt(t,{end:.3f}),0.55,0.15)':eval=frame,"
            f"afade=t=out:st={fade:.3f}:d=1.2[m{n}]"
        )
        mix.append(f"[m{n}]")
        n += 1
    graph = ";".join([video, *audio, f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=longest,alimiter=limit=0.95[a]"])
    args += ["-filter_complex", graph, "-map", "[v]", "-map", "[a]", "-t", f"{total:.3f}",
             "-c:v", "libx264", "-crf", str(CRF), "-preset", "veryfast", "-c:a", "aac", "-b:a", "128k",
             "-movflags", "+faststart", str(target)]
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=3600)
    except (OSError, subprocess.SubprocessError):
        return False
    if out.returncode != 0:
        print(out.stderr[-2000:])
    return out.returncode == 0 and target.exists()
