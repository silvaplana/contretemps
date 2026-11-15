"""Noter les gestes dans la frise d'une séance filmée (Seb, 15/11) : Bon,
Mauvais (puis le vrai geste) ou Inventé sous chaque geste repéré, et « Il
manque un geste ici ». « Proposer un réglage » essaie alors chaque durée
minimale d'un geste sur toutes les séances notées et dit laquelle colle le
mieux aux notes ; rien ne change sans « Appliquer » (le PUT des Paramètres
de tournage).

Un fichier par séance, sans table : `gesture-notes/<séance>.json` = la liste
des notes `{t, kind, answer, real}` (secondes dans la séance)."""

from __future__ import annotations

import json
from pathlib import Path

from videos.stockage import dossier_ecole

from .fights import find_signs
from .lab import MAX_HOLD, MIN_HOLD
from .ports import Member
from .service import ForbiddenError, NotFoundError
from .signals import Frame

GESTURES = ("fists_touch", "arms_up", "handshake", "x")
ANSWERS = ("good", "wrong", "invented", "missing")
NEAR = 1.5  # un geste repéré à 1,5 s d'une note est le geste noté
AROUND = 10.0  # seules les images à 10 s d'une note sont relues


def _path(member: Member, session_id: int) -> Path:
    if not member.is_coach:
        raise ForbiddenError("Réservé aux coachs")
    return dossier_ecole(member.org_id) / "gesture-notes" / f"{int(session_id)}.json"


def notes(member: Member, session_id: int) -> list[dict]:
    path = _path(member, session_id)
    return json.loads(path.read_text()) if path.exists() else []


def note(member: Member, session_id: int, t: float, kind: str, answer: str, real: str | None) -> list[dict]:
    if kind not in GESTURES or answer not in ANSWERS or (real is not None and real not in GESTURES):
        raise ValueError("Note inconnue")
    old = [n for n in notes(member, session_id) if abs(n["t"] - t) >= 0.3 or n["kind"] != kind]
    out = sorted([*old, {"t": round(t, 2), "kind": kind, "answer": answer, "real": real}], key=lambda n: n["t"])
    path = _path(member, session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out))
    return out


def unnote(member: Member, session_id: int, t: float) -> list[dict]:
    old = notes(member, session_id)
    out = [n for n in old if abs(n["t"] - t) >= 0.3]
    if len(out) == len(old):
        raise NotFoundError("Note introuvable")
    _path(member, session_id).write_text(json.dumps(out))
    return out


def noted_sessions(member: Member) -> dict[int, list[dict]]:
    """Les séances notées de l'école : {séance: notes}."""
    folder = _path(member, 0).parent
    found = {int(p.stem): json.loads(p.read_text()) for p in folder.glob("*.json") if p.stem.isdigit()} if folder.exists() else {}
    return {k: v for k, v in found.items() if v}


def _expected(n: dict) -> list[tuple[str, bool]]:
    """Ce qu'une note attend autour de son moment : (geste, repéré ou non)."""
    if n["answer"] in ("good", "missing"):
        return [(n["kind"], True)]
    return [(n["kind"], False)] + ([(n["real"], True)] if n.get("real") else [])


def score(frames: list[Frame], marks: list[dict], hold: float) -> int:
    """Le nombre d'attentes des notes que la durée `hold` respecte."""
    signs = find_signs(frames, (), hold)
    right = 0
    for n in marks:
        for kind, wanted in _expected(n):
            seen = any(s.kind == kind and abs(s.start - n["t"]) <= NEAR for s in signs)
            right += seen == wanted
    return right


def propose(sessions: list[tuple[list[Frame], list[dict]]], current: float) -> dict:
    """Essaie chaque durée de 0,4 à 3 s (par 0,1 s) sur les séances notées.
    Renvoie le réglage du jour et le meilleur (à égalité, le plus proche du
    réglage du jour), avec le nombre d'attentes justes sur le total."""
    near = [
        ([f for f in frames if any(abs(f.t - n["t"]) <= AROUND for n in marks)], marks) for frames, marks in sessions
    ]
    total = sum(len(_expected(n)) for _, marks in near for n in marks)
    right = lambda hold: sum(score(frames, marks, hold) for frames, marks in near)  # noqa: E731
    holds = [round(MIN_HOLD + i / 10, 1) for i in range(int(round((MAX_HOLD - MIN_HOLD) * 10)) + 1)]
    scores = {h: right(h) for h in holds}
    now = right(current)
    best = max(holds, key=lambda h: (scores[h], -abs(h - current)))
    if scores[best] <= now:  # rien de mieux : garder le réglage du jour
        best, scores[best] = current, now
    return {
        "total": total,
        "sessions": len(near),
        "current": {"min_hold": current, "right": now},
        "best": {"min_hold": best, "right": scores[best]},
    }
