"""Fights › ⋮ › Entraîner l'écoute (spec/modules/video-combats.md §5, Seb
14/11) : des enregistrements des cris, dits au téléphone, pour apprendre ces
mots à l'écoute plus tard (Whisper invente des mots sur les passages calmes).

Pas de table : un fichier par enregistrement, dans le dossier de l'école
(`<VIDEOS_DIR>/<école>/voice/<mot>/<nom>.webm`), le mot étant le dossier."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

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


def delete(member: Member, word: str, name: str) -> None:
    path(member, word, name).unlink()
