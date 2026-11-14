"""Montre ce que le serveur a vu dans les séances filmées par la caméra de
Fights, pour comprendre une découpe ratée (Seb, 13/11/2026 : action
« Maintenance du VPS », DEPLOY.md §6). N'écrit rien.

    python -m app.lire_seance_fights             # les 10 dernières séances
    python -m app.lire_seance_fights --seance 12 # le détail d'une séance

Le détail donne chaque morceau (fichier, durée, rotation), les sons
entendus, le nombre de personnes vues seconde par seconde, les signes et
les combats que la découpe trouve avec les réglages du jour.
"""

from __future__ import annotations

import argparse
import json
import subprocess

import imageio_ffmpeg
from sqlalchemy import select

from app import main  # noqa: F401  (toutes les tables connues de SQLAlchemy)
from db import SessionLocal
from saisons.portee import toutes_saisons
from session_clips import lab
from session_clips.cutting import _heard, _load_frames, _poses_path
from session_clips.fights import find_fights, find_signs, trim
from session_clips.models import Clip, ClipSession, Piece
from session_clips.signals import (
    L_SHOULDER,
    L_WRIST,
    R_SHOULDER,
    R_WRIST,
    Frame,
    Pose,
    _shoulders_top,
    _wrists,
    is_x,
    main_pair,
    torso,
    upright,
)
from videos import Video
from videos.stockage import DOSSIER_VIDEOS_LIVE


def _pieces(db, session_id: int) -> list[Piece]:
    return list(db.scalars(select(Piece).where(Piece.session_id == session_id).order_by(Piece.position)))


def lister(db, out=print) -> None:
    for x in db.scalars(select(ClipSession).order_by(ClipSession.id.desc()).limit(10)):
        pieces = _pieces(db, x.id)
        filmed = sum(p.duration_seconds or 0 for p in pieces)
        clips = db.scalars(select(Clip).where(Clip.session_id == x.id)).all()
        signs = json.loads(x.signs) if x.signs else []
        fin = f"{x.ended_at:%H:%M:%S}" if x.ended_at else "…"
        out(f"séance {x.id} · école {x.org_id} · {x.title} · {x.status} · {x.created_at:%d/%m %H:%M:%S} → {fin} (UTC)")
        out(
            f"   {len(pieces)} morceaux, {filmed:.1f} s lues · {len(clips)} combats · signes : "
            + (", ".join(f"{s['kind']} {s['start']}" for s in signs) or "aucun")
        )


def detail(db, session_id: int, out=print) -> None:
    x = db.get(ClipSession, session_id)
    if x is None:
        out("Séance introuvable.")
        return
    out(f"séance {x.id} · école {x.org_id} · {x.title} · {x.status} · début {x.created_at} · fin {x.ended_at}")
    frames: list[Frame] = []
    sounds = []
    offset = 0.0
    for p in _pieces(db, x.id):
        video = db.get(Video, p.video_id) if p.video_id else None
        out(f"morceau {p.position} · dernier={p.last} · durée lue {p.duration_seconds} · vidéo {video.statut if video else 'aucune'}")
        if video is not None:
            path = DOSSIER_VIDEOS_LIVE / video.lien_fichier
            out(f"  fichier {video.lien_fichier} · {path.stat().st_size if path.exists() else 'absent'} octets")
            info = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(path)], capture_output=True, text=True, check=False)
            for line in info.stderr.splitlines():
                if any(k in line for k in ("Duration", "Stream", "rotat", "displaymatrix")):
                    out("    " + line.strip())
        poses = _poses_path(x.org_id, p.id)
        heard = poses.with_suffix(".sounds.json")
        if heard.exists():
            out(f"  sons entendus : {heard.read_text()}")
            sounds += [(k, t + offset) for k, t in _heard(heard, p.duration_seconds or 0)]
        if poses.exists():
            piece_frames = _load_frames(poses)
            per_second: dict[int, int] = {}
            for f in piece_frames:
                per_second[int(f.t)] = max(per_second.get(int(f.t), 0), len(f.people))
            out("  personnes vues par seconde : " + " ".join(f"{t}:{n}" for t, n in sorted(per_second.items())))
            frames += [Frame(t=f.t + offset, people=f.people) for f in piece_frames]
        else:
            out("  pas de postures gardées")
        offset += p.duration_seconds or 0
    # Vidéo couchée : l'analyse lit les postures redressées (fights.upright, Seb 14/11).
    if (straight := upright(frames)) is not frames:
        out("vidéo couchée : postures redressées d'un quart de tour")
    _raised(straight, out)
    _crossed(straight, out)
    _report(frames, sounds, lab.settings(db, x.org_id), out)
    for c in db.scalars(select(Clip).where(Clip.session_id == x.id).order_by(Clip.position)):
        out(f"combat coupé {c.position} · début {c.start_seconds} · à vérifier={c.to_check}")


def _report(frames: list[Frame], sounds, s, out) -> None:
    out(f"réglages du tournage : signes {list(s.signs)}, cadrage {s.framing}, début -{s.start_skip} s, fin -{s.end_skip} s")
    out(f"signes recalculés : {[(g.kind, round(g.start, 1), round(g.end, 1)) for g in find_signs(frames, sounds)]}")
    fights = trim(find_fights(frames, s.signs, sounds), s.start_skip, s.end_skip)
    out(f"combats avec les règles du jour : {[(round(f.start, 1), round(f.end, 1), f.check_reason) for f in fights]}")


def _raised(frames: list[Frame], out, limit: int = 200) -> None:
    """Les images où les deux combattants ont un poignet bien au-dessus des
    épaules : l'écart entre leurs poignets les plus proches et leur hauteur,
    en bustes, pour régler les poings touchés (Seb, 13/11, séance 9)."""
    lines = []
    for f in frames:
        pair = main_pair(f)
        if len(pair) != 2:
            continue
        unit = min(torso(p) or 0 for p in pair)
        tops = [_shoulders_top(p) for p in pair]
        if not unit or None in tops:
            continue
        ups = [[w for w in _wrists(p) if w[1] < top - 0.2 * unit] for p, top in zip(pair, tops, strict=True)]
        if not all(ups):
            continue
        gap = min(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 for a in ups[0] for b in ups[1]) / unit
        lift = [round((top - min(w[1] for w in u)) / unit, 2) for u, top in zip(ups, tops, strict=True)]
        lines.append(f"  {f.t:6.1f} s · écart des poignets {gap:.2f} buste · hauteur au-dessus des épaules {lift}")
    out(f"bras levés tous les deux : {len(lines)} images (poings touchés : écart < 0,35, ou < 0,65 si hauteur ≥ 0,4)")
    for line in lines[:limit]:
        out(line)


def _cross_check(p: Pose) -> str:
    """Pourquoi une personne n'a pas les bras croisés (is_x) : point manquant,
    poignets sous les hanches, de profil (écart des épaules / buste), poignets
    pas croisés, ou X."""
    points = [p.point(i) for i in (L_SHOULDER, R_SHOULDER, L_WRIST, R_WRIST)]
    unit = torso(p)
    if None in points or not unit:
        return "?" + "".join(n for n, q in zip(("ég", "éd", "pg", "pd"), points, strict=True) if q is None)
    l_sh, r_sh, l_wr, r_wr = points
    if l_wr[1] >= l_sh[1] + unit or r_wr[1] >= l_sh[1] + unit:
        return "bas"
    face = abs(l_sh[0] - r_sh[0]) / unit
    if face < 1 / 3:
        return f"profil {face:.2f}"
    return "X" if is_x(p) else f"pas croisés {face:.2f}"


def _crossed(frames: list[Frame], out) -> None:
    """Seconde par seconde, ce que voit le test des bras croisés pour chacun
    des deux combattants (Seb, 14/11 : séance 9, bras croisés à 0:36 non vus)."""
    out("bras croisés, seconde par seconde (? = point manquant, profil = épaules / buste < 0,33) :")
    by_second: dict[int, list[str]] = {}
    for f in frames:
        pair = main_pair(f)
        if len(pair) == 2:
            by_second.setdefault(int(f.t), []).append(" | ".join(_cross_check(p) for p in pair))
    for t, seen in sorted(by_second.items()):
        out(f"  {t:4d} s · " + " ; ".join(dict.fromkeys(seen)))


def run() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seance", type=int, help="numéro de la séance")
    args = parser.parse_args()
    with SessionLocal() as db, toutes_saisons(db):
        if args.seance is None:
            lister(db)
        else:
            detail(db, args.seance)


if __name__ == "__main__":
    run()
