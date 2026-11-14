"""Fights › ⋮ › Entraîner l'écoute (spec/modules/video-combats.md §5, Seb
14/11) : des enregistrements des cris, dits au téléphone, pour apprendre ces
mots à l'écoute plus tard (Whisper invente des mots sur les passages calmes).

Pas de table : un fichier par enregistrement, dans le dossier de l'école
(`<VIDEOS_DIR>/<école>/voice/<mot>/<nom>.webm`), le mot étant le dossier."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from videos import stockage
from videos.stockage import dossier_ecole

from .ports import Member
from .service import ForbiddenError, NotFoundError

WORDS = ("fight", "hajime", "combat", "time")
MAX_BYTES = 2_000_000  # quelques secondes de son
EXTENSIONS = {"audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mp4": ".m4a", "audio/aac": ".aac"}
_NAME = re.compile(r"^[0-9a-f]{32}\.(webm|ogg|m4a|aac)$")


def _folder(member: Member, word: str) -> Path:
    if not member.is_coach:
        raise ForbiddenError("Réservé aux coachs")
    if word not in WORDS:
        raise ValueError("Mot inconnu")
    return dossier_ecole(member.org_id) / "voice" / word


def samples(member: Member) -> dict[str, list[str]]:
    """Les enregistrements de chaque mot, les plus récents d'abord."""
    out = {}
    for word in WORDS:
        folder = _folder(member, word)
        files = sorted(folder.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True) if folder.exists() else []
        out[word] = [p.name for p in files if _NAME.match(p.name)]
    return out


def add(member: Member, word: str, data: bytes, content_type: str) -> dict[str, list[str]]:
    folder = _folder(member, word)
    if not data or len(data) > MAX_BYTES:
        raise ValueError("Enregistrement vide ou trop long")
    folder.mkdir(parents=True, exist_ok=True)
    extension = EXTENSIONS.get(content_type.split(";")[0].strip(), ".webm")
    (folder / f"{uuid.uuid4().hex}{extension}").write_bytes(data)
    return samples(member)


def path(member: Member, word: str, name: str) -> Path:
    found = _folder(member, word) / name
    if not _NAME.match(name) or not found.exists():
        raise NotFoundError("Enregistrement introuvable")
    return found


def newest(org_id: int) -> float:
    """L'heure du dernier changement des cris enregistrés (0 s'il n'y en a pas) :
    l'écoute du club réécoute les morceaux écoutés avant (cutting.py)."""
    folder = dossier_ecole(org_id) / "voice"
    stamps = [p.stat().st_mtime for p in folder.glob("*")] + [p.stat().st_mtime for p in folder.glob("*/*")]
    return max(stamps, default=0.0)


def delete(member: Member, word: str, name: str) -> None:
    path(member, word, name).unlink()


# --- Tester l'écoute (Seb, 14/11) : 10 s enregistrées, écoutées par le
# worker avec l'écoute du club, les mots reconnus montrés sur la page. ---

KEEP_TESTS = 5  # les plus anciens essais sont effacés


def _tests_folder(member: Member) -> Path:
    if not member.is_coach:
        raise ForbiddenError("Réservé aux coachs")
    return dossier_ecole(member.org_id) / "voice-tests"


def add_test(member: Member, data: bytes, content_type: str) -> str:
    folder = _tests_folder(member)
    if not data or len(data) > MAX_BYTES * 5:
        raise ValueError("Enregistrement vide ou trop long")
    folder.mkdir(parents=True, exist_ok=True)
    old = sorted(folder.glob("*"), key=lambda p: p.stat().st_mtime)
    for p in old[: max(len(old) - 2 * (KEEP_TESTS - 1), 0)]:
        p.unlink()
    name = f"{uuid.uuid4().hex}{EXTENSIONS.get(content_type.split(';')[0].strip(), '.webm')}"
    (folder / name).write_bytes(data)
    return name


def test_result(member: Member, name: str) -> dict:
    found = _tests_folder(member) / name
    if not _NAME.match(name) or not found.exists():
        raise NotFoundError("Essai introuvable")
    result = found.with_suffix(".json")
    if not result.exists():
        return {"done": False, "words": []}
    words = json.loads(result.read_text())
    return {"done": True, "words": [{"kind": k, "t": t, "note": n, "db": db} for k, t, n, db in words]}


def hear_tests(hear) -> int:
    """Pour le worker : écoute les essais pas encore écoutés, toutes écoles."""
    n = 0
    for path in sorted(stockage.DOSSIER_VIDEOS_LIVE.glob("*/voice-tests/*")):
        if _NAME.match(path.name) and not path.with_suffix(".json").exists():
            path.with_suffix(".json").write_text(json.dumps(hear(path, "club")))
            n += 1
    return n
