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
_NAME = re.compile(r"^[0-9a-f]{32}\.(webm|ogg|m4a|aac|wav)$")
# Les exemples de ce qui n'est pas un mot (Seb, 14/11, après un test) : un autre
# mot (« Mauvais ») ou rien du tout (« Inventé »). Hors de la page, servent à
# l'écoute du club (club_hearing.py).
NOT_WORDS = ("other", "noise")
ANSWERS = ("good", "wrong", "invented")


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

def _tests_folder(member: Member) -> Path:
    if not member.is_coach:
        raise ForbiddenError("Réservé aux coachs")
    return dossier_ecole(member.org_id) / "voice-tests"


def add_test(member: Member, data: bytes, content_type: str) -> str:
    folder = _tests_folder(member)
    if not data or len(data) > MAX_BYTES * 5:
        raise ValueError("Enregistrement vide ou trop long")
    # Tous gardés (Seb, 14/11 : pour apprendre dessus ; environ 100 Ko chacun).
    folder.mkdir(parents=True, exist_ok=True)
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


def answer_test(member: Member, name: str, t: float, answer: str, word: str | None) -> None:
    """Bon, Mauvais ou Inventé sous un mot trouvé (Seb, 14/11) : 2 s autour du
    moment, coupées dans l'essai, rangées comme exemple du mot (Bon), du mot
    dit (Mauvais : un des mots, ou « other » pour un autre mot), ou de rien
    (Inventé : « noise »)."""
    import subprocess

    import imageio_ffmpeg

    source = _tests_folder(member) / name
    if not _NAME.match(name) or not source.exists():
        raise NotFoundError("Essai introuvable")
    if answer not in ANSWERS:
        raise ValueError("Réponse inconnue")
    folder_name = "noise" if answer == "invented" else word
    if folder_name not in WORDS + NOT_WORDS or (answer == "good" and word not in WORDS):
        raise ValueError("Mot inconnu")
    folder = dossier_ecole(member.org_id) / "voice" / folder_name
    folder.mkdir(parents=True, exist_ok=True)
    example = f"{uuid.uuid4().hex}.wav"
    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-nostdin", "-y", "-loglevel", "error", "-ss", f"{max(t - 0.5, 0):.2f}", "-t", "2",
         "-i", str(source), "-vn", "-ac", "1", "-ar", "16000", str(folder / example)],
        check=True,
    )
    # La vérité du test, pour « Rejouer tous les essais » : le mot dit à ce
    # moment (« other » : un autre mot ; None : rien), et l'exemple qui en vient.
    _add_truth(source, {"t": t, "word": None if answer == "invented" else word, "example": f"{folder_name}/{example}"})


def _add_truth(source: Path, entry: dict) -> None:
    path = source.with_suffix(".truth.json")
    truth = json.loads(path.read_text()) if path.exists() else []
    path.write_text(json.dumps([*truth, entry]))


def missing_word(member: Member, name: str, word: str) -> None:
    """« Il manque un mot » (Seb, 14/11) : un mot crié pendant le test que l'écoute n'a pas trouvé."""
    source = _tests_folder(member) / name
    if not _NAME.match(name) or not source.exists():
        raise NotFoundError("Essai introuvable")
    if word not in WORDS:
        raise ValueError("Mot inconnu")
    _add_truth(source, {"t": None, "word": word, "example": None})


# --- Rejouer tous les essais (Seb, 14/11) : les points de l'écoute du club
# sur tous les tests répondus, pour suivre ses progrès. ---

NEAR = 1.0  # secondes : un mot trouvé à moins d'1 s d'une réponse en parle


def score(found: list, truth: list[dict]) -> dict:
    """+1 par bon mot, −1 par mauvais mot, −2 par mot inventé, −1 par mot
    oublié (Seb, 14/11) ; « best » : les points d'une écoute parfaite."""
    timed = [x for x in truth if x["t"] is not None]
    missing = [x["word"] for x in truth if x["t"] is None]
    best = sum(1 for x in timed if x["word"] in WORDS) + len(missing)
    used: set[int] = set()
    good = wrong = invented = 0
    for kind, t, *_rest in found:
        near = [i for i, x in enumerate(timed) if i not in used and abs(x["t"] - t) <= NEAR]
        if near:
            i = min(near, key=lambda i: abs(timed[i]["t"] - t))
            used.add(i)
            said = timed[i]["word"]
            if said == kind:
                good += 1
            elif said is None:
                invented += 1
            else:
                wrong += 1
        elif kind in missing:
            missing.remove(kind)
            good += 1
        else:
            invented += 1
    missed = len(missing) + sum(1 for i, x in enumerate(timed) if i not in used and x["word"] in WORDS)
    points = good - wrong - 2 * invented - missed
    return {"good": good, "wrong": wrong, "invented": invented, "missed": missed, "points": points, "best": best}


def _replays_folder(member: Member) -> Path:
    if not member.is_coach:
        raise ForbiddenError("Réservé aux coachs")
    return dossier_ecole(member.org_id) / "voice-replays"


def add_replay(member: Member) -> None:
    folder = _replays_folder(member)
    folder.mkdir(parents=True, exist_ok=True)
    import time

    (folder / f"{int(time.time() * 1000)}.json").write_text(json.dumps({"done": False}))


def replays(member: Member) -> list[dict]:
    """L'historique des rejeux, du plus ancien au plus récent."""
    folder = _replays_folder(member)
    files = sorted(folder.glob("*.json"), key=lambda p: int(p.stem)) if folder.exists() else []
    return [{"at": int(p.stem) / 1000, **json.loads(p.read_text())} for p in files]


def run_replays(hear) -> int:
    """Pour le worker : rejoue les demandes en attente, toutes écoles.
    `hear(chemin, exemples à écarter)` : l'écoute du club sans les exemples
    venus du test rejoué (sinon elle se reconnaîtrait elle-même)."""
    n = 0
    for request in sorted(stockage.DOSSIER_VIDEOS_LIVE.glob("*/voice-replays/*.json")):
        if json.loads(request.read_text()).get("done"):
            continue
        school = request.parent.parent
        totals = {"good": 0, "wrong": 0, "invented": 0, "missed": 0, "points": 0, "best": 0}
        tests = 0
        for path in sorted((school / "voice-tests").glob("*")):
            truth_path = path.with_suffix(".truth.json")
            if not _NAME.match(path.name) or not truth_path.exists():
                continue
            truth = json.loads(truth_path.read_text())
            exclude = frozenset(x["example"] for x in truth if x.get("example"))
            for k, v in score(hear(path, exclude), truth).items():
                totals[k] += v
            tests += 1
        examples = sum(1 for p in (school / "voice").glob("*/*") if p.parent.name in WORDS and _NAME.match(p.name))
        request.write_text(json.dumps({"done": True, "tests": tests, "examples": examples, **totals}))
        n += 1
    return n
