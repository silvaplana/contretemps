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

# « fight » retiré le 14/11 (Seb : même « aï » que « Time ») ; ses
# enregistrements restent sur le disque, l'écoute ne les lit plus.
# « combat » remplacé par « combattez » le 15/11 (Seb : trois syllabes, finit
# en « é », moins inventé) ; ses enregistrements restent dans voice/combat/, non lus.
WORDS = ("hajime", "combattez", "time")
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


# Le cri entier comparé dans l'ordre (étude du 14/11), puis les cris
# « presque » gardés pour la frise (15/11, vers 1 h 45 à Paris) : les
# morceaux écoutés avant sont réécoutés.
CLUB_CHANGED = 1794703200.0  # 2026-11-15 00:40 UTC


def newest(org_id: int) -> float:
    """L'heure du dernier changement des cris enregistrés ou du réglage du
    rejeu : l'écoute du club réécoute les morceaux écoutés avant (cutting.py)."""
    school = dossier_ecole(org_id)
    folder = school / "voice"
    stamps = [p.stat().st_mtime for p in folder.glob("*")] + [p.stat().st_mtime for p in folder.glob("*/*")]
    tuned = school / "voice-replays" / "thresholds.json"
    if tuned.exists():
        stamps.append(tuned.stat().st_mtime)
    return max([*stamps, CLUB_CHANGED])


def delete(member: Member, word: str, name: str) -> None:
    path(member, word, name).unlink()


def reset(member: Member) -> None:
    """« Effacer les enregistrements » (Seb, 14/11) : tous les cris de
    l'école, y compris les exemples rangés par Bon / Mauvais / Inventé. Le
    dossier `voice/` vide reste, daté de maintenant : newest() fait
    réécouter les morceaux écoutés avant avec l'écoute du club."""
    import shutil

    folder = _folder(member, WORDS[0]).parent
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)


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


def reset_tests(member: Member) -> None:
    """« Effacer les tests » (Seb, 14/11) : les tests, leurs réponses et
    l'historique des points ; les cris enregistrés restent."""
    import shutil

    folder = _tests_folder(member)
    shutil.rmtree(folder, ignore_errors=True)
    shutil.rmtree(folder.parent / "voice-replays", ignore_errors=True)
    shutil.rmtree(folder.parent / "voice-sessions", ignore_errors=True)


def test_result(member: Member, name: str) -> dict:
    found = _tests_folder(member) / name
    if not _NAME.match(name) or not found.exists():
        raise NotFoundError("Essai introuvable")
    result = found.with_suffix(".json")
    if not result.exists():
        return {"done": False, "words": []}
    words = json.loads(result.read_text())
    # Sans les « presque » (5e élément) : seuls les mots retenus sont à juger.
    return {"done": True, "words": [{"kind": k, "t": t, "note": n, "db": db} for k, t, n, db, *weak in words if not any(weak)]}


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
    source = _tests_folder(member) / name
    if not _NAME.match(name) or not source.exists():
        raise NotFoundError("Essai introuvable")
    folder_name = _answer_folder(answer, word)
    example = _cut(member, source, t, folder_name)
    # La vérité du test, pour « Rejouer tous les essais » : le mot dit à ce
    # moment (« other » : un autre mot ; None : rien), et l'exemple qui en vient.
    _add_truth(source, {"t": t, "word": None if answer == "invented" else word, "example": example})


def _answer_folder(answer: str, word: str | None) -> str:
    if answer not in ANSWERS:
        raise ValueError("Réponse inconnue")
    folder_name = "noise" if answer == "invented" else word
    if folder_name not in WORDS + NOT_WORDS or (answer == "good" and word not in WORDS):
        raise ValueError("Mot inconnu")
    return folder_name


def _cut(member: Member, source: Path, t: float, folder_name: str) -> str:
    """2 s de `source` à partir de t − 0,5 s, rangées dans voice/<dossier>/ ; renvoie « dossier/fichier »."""
    import subprocess

    import imageio_ffmpeg

    folder = dossier_ecole(member.org_id) / "voice" / folder_name
    folder.mkdir(parents=True, exist_ok=True)
    example = f"{uuid.uuid4().hex}.wav"
    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-nostdin", "-y", "-loglevel", "error", "-ss", f"{max(t - 0.5, 0):.2f}", "-t", "2",
         "-i", str(source), "-vn", "-ac", "1", "-ar", "16000", str(folder / example)],
        check=True,
    )
    return f"{folder_name}/{example}"


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


# --- Noter les cris d'une séance filmée (étude du 14/11) : la même vérité
# que pour un test, sur le vrai son de la salle, comptée par le rejeu.
# Un fichier par séance : `voice-sessions/<séance>.json` = les morceaux
# (chemin sous VIDEOS_DIR, début dans la séance, durée) et la vérité. ---

def _session_path(member: Member, session_id: int) -> Path:
    if not member.is_coach:
        raise ForbiddenError("Réservé aux coachs")
    return dossier_ecole(member.org_id) / "voice-sessions" / f"{int(session_id)}.json"


def session_truth(member: Member, session_id: int) -> list[dict]:
    path = _session_path(member, session_id)
    return json.loads(path.read_text())["truth"] if path.exists() else []


def note_session(member: Member, session_id: int, pieces: list[tuple[str, float, float]], t: float, answer: str,
                 word: str | None) -> list[dict]:
    """Bon, Mauvais, Inventé sous un cri de la séance, ou « Il manque un
    mot » (`answer` = "missing", au moment de la vidéo) : 2 s coupées dans le
    morceau, rangées comme exemple, et la vérité de la séance complétée.
    `pieces` : (chemin sous VIDEOS_DIR, début dans la séance, durée)."""
    if answer == "missing":
        if word not in WORDS:
            raise ValueError("Mot inconnu")
        folder_name = word
    else:
        folder_name = _answer_folder(answer, word)
    here = next(((p, off) for p, off, length in pieces if off <= t < off + length), None)
    if here is None:
        raise NotFoundError("Moment hors de la vidéo")
    path = _session_path(member, session_id)
    example = _cut(member, stockage.DOSSIER_VIDEOS_LIVE / here[0], t - here[1], folder_name)
    old = json.loads(path.read_text())["truth"] if path.exists() else []
    truth = [*old, {"t": round(t, 2), "word": None if answer == "invented" else word, "example": example}]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"pieces": [list(p) for p in pieces], "truth": truth}))
    return truth


def unnote_session(member: Member, session_id: int, t: float) -> list[dict]:
    """Retire une note mise par erreur (Seb, 15/11 : un « Time » de trop) :
    la ligne de la vérité au moment `t` (à 0,3 s près) et l'exemple qui en venait."""
    path = _session_path(member, session_id)
    noted = json.loads(path.read_text()) if path.exists() else {"pieces": [], "truth": []}
    found = next((x for x in noted["truth"] if abs(x["t"] - t) < 0.3), None)
    if found is None:
        raise NotFoundError("Note introuvable")
    if found.get("example"):
        folder, name = found["example"].split("/")
        if folder in WORDS + NOT_WORDS and _NAME.match(name):
            (dossier_ecole(member.org_id) / "voice" / folder / name).unlink(missing_ok=True)
    noted["truth"] = [x for x in noted["truth"] if x is not found]
    path.write_text(json.dumps(noted))
    return noted["truth"]


# --- Rejouer tous les essais (Seb, 14/11) : les points de l'écoute du club
# sur tous les tests répondus, pour suivre ses progrès. ---

NEAR = 1.0  # secondes : un mot trouvé à moins d'1 s d'une réponse en parle


def score(found: list, truth: list[dict]) -> dict:
    """+1 par bon mot, −1 par mauvais mot, −2 par mot inventé, −1 par mot
    oublié (Seb, 14/11) ; « best » : les points d'une écoute parfaite.
    « words » : le détail mot par mot (étude du 14/11, pour choisir le mot
    du début) : bons, oubliés, inventés (trouvé sans rien de dit), mauvais
    (trouvé à la place d'un autre mot) et « heard_as » (dit, mais trouvé
    comme quel mot)."""
    timed = [x for x in truth if x["t"] is not None]
    missing = [x["word"] for x in truth if x["t"] is None]
    best = sum(1 for x in timed if x["word"] in WORDS) + len(missing)
    words = {w: {"good": 0, "missed": 0, "invented": 0, "wrong": 0, "heard_as": {}} for w in WORDS}

    def count(word, key, other=None):
        if word not in words:
            return
        if key == "heard_as":
            words[word][key][other] = words[word][key].get(other, 0) + 1
        else:
            words[word][key] += 1

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
                count(kind, "good")
            elif said is None:
                invented += 1
                count(kind, "invented")
            else:
                wrong += 1
                count(kind, "wrong")
                count(said, "heard_as", kind)
        elif kind in missing:
            missing.remove(kind)
            good += 1
            count(kind, "good")
        else:
            invented += 1
            count(kind, "invented")
    forgotten = missing + [x["word"] for i, x in enumerate(timed) if i not in used and x["word"] in WORDS]
    for word in forgotten:
        count(word, "missed")
    missed = len(forgotten)
    points = good - wrong - 2 * invented - missed
    return {"good": good, "wrong": wrong, "invented": invented, "missed": missed, "points": points, "best": best, "words": words}


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
    files = sorted((p for p in folder.glob("*.json") if p.stem.isdigit()), key=lambda p: int(p.stem)) if folder.exists() else []
    return [{"at": int(p.stem) / 1000, **json.loads(p.read_text())} for p in files]


# Les réglages essayés par le rejeu (étude du 14/11) : le seuil de
# ressemblance au mot, et l'avance sur le 2e mot (ou sur un faux cri signalé).
SCORES = tuple(round(x * 0.05, 2) for x in range(-4, 19))  # −0,2 à 0,9
MARGINS = (0.0, 0.01, 0.02, 0.05, 0.1, 0.15, 0.2)


def _tune(heard: list[tuple[list, list[dict]]]) -> tuple[float, float]:
    """Le seuil et l'écart qui donnent le plus de points sur tous les tests
    (à points égaux, les plus sévères : moins de mots inventés)."""
    from .club_hearing import pick

    def total(s: float, m: float) -> int:
        return sum(score(pick(found, s, m), truth)["points"] for found, truth in heard)

    return max(((s, m) for s in SCORES for m in MARGINS), key=lambda x: (total(*x), x[0], x[1]))


def run_replays(hear) -> int:
    """Pour le worker : rejoue les demandes en attente, toutes écoles.
    `hear(chemin, exemples à écarter)` : l'écoute du club sans les exemples
    venus du test rejoué (sinon elle se reconnaîtrait elle-même), avant le
    seuil. Le rejeu règle le seuil et l'écart (`voice-replays/thresholds.json`),
    que l'écoute du club prend ensuite pour les séances et les tests."""
    from .club_hearing import pick

    n = 0
    for request in sorted(stockage.DOSSIER_VIDEOS_LIVE.glob("*/voice-replays/*.json")):
        if not request.stem.isdigit() or json.loads(request.read_text()).get("done"):
            continue
        school = request.parent.parent
        heard = []
        for path in sorted((school / "voice-tests").glob("*")):
            truth_path = path.with_suffix(".truth.json")
            if not _NAME.match(path.name) or not truth_path.exists():
                continue
            truth = json.loads(truth_path.read_text())
            exclude = frozenset(x["example"] for x in truth if x.get("example"))
            heard.append((hear(path, exclude), truth))
        # Les séances notées : chaque morceau écouté, ses cris remis à l'heure de la séance.
        for path in sorted((school / "voice-sessions").glob("*.json")):
            noted = json.loads(path.read_text())
            exclude = frozenset(x["example"] for x in noted["truth"] if x.get("example"))
            found = [
                (k, round(t + offset, 1), *rest)
                for piece, offset, _length in noted["pieces"]
                for k, t, *rest in hear(stockage.DOSSIER_VIDEOS_LIVE / piece, exclude)
            ]
            heard.append((found, noted["truth"]))
        min_score, min_margin = _tune(heard) if heard else (None, None)
        totals = {"good": 0, "wrong": 0, "invented": 0, "missed": 0, "points": 0, "best": 0}
        by_word = {w: {"good": 0, "missed": 0, "invented": 0, "wrong": 0, "heard_as": {}} for w in WORDS}
        for found, truth in heard:
            result = score(pick(found, min_score, min_margin), truth)
            for k in totals:
                totals[k] += result[k]
            for w, counts in result["words"].items():
                for k, v in counts.items():
                    if k == "heard_as":
                        for other, c in v.items():
                            by_word[w][k][other] = by_word[w][k].get(other, 0) + c
                    else:
                        by_word[w][k] += v
        if heard:
            (request.parent / "thresholds.json").write_text(json.dumps({"min_score": min_score, "min_margin": min_margin}))
        examples = sum(1 for p in (school / "voice").glob("*/*") if p.parent.name in WORDS and _NAME.match(p.name))
        request.write_text(json.dumps({
            "done": True, "tests": len(heard), "examples": examples, **totals, "words": by_word,
            "min_score": min_score, "min_margin": min_margin,
        }))
        n += 1
    return n


def recover_truths(read_audio) -> int:
    """Retrouve les réponses données avant que la vérité soit gardée (Seb,
    14/11) : chaque exemple .wav vient de 2 s coupées dans un test, à partir
    de t − 0,5 s. On le cherche dans les tests faits avant lui (le plus
    récent d'abord) et on ajoute la réponse à la vérité de ce test. Ne
    touche à rien d'autre ; rejouable. Renvoie le nombre de réponses retrouvées."""
    import numpy as np

    found = 0
    for school in sorted(p for p in stockage.DOSSIER_VIDEOS_LIVE.glob("*") if (p / "voice-tests").is_dir()):
        tests = sorted(
            (p for p in (school / "voice-tests").glob("*") if _NAME.match(p.name)), key=lambda p: p.stat().st_mtime
        )
        known = {
            x.get("example")
            for p in tests
            if p.with_suffix(".truth.json").exists()
            for x in json.loads(p.with_suffix(".truth.json").read_text())
        }
        audio_cache: dict = {}
        for example in sorted((school / "voice").glob("*/*.wav")):
            key = f"{example.parent.name}/{example.name}"
            if key in known or example.parent.name not in WORDS + NOT_WORDS:
                continue
            clip = np.asarray(read_audio(example), dtype=np.float64)
            if len(clip) < 1600 or not clip.any():
                continue
            before = [p for p in tests if p.stat().st_mtime <= example.stat().st_mtime + 1][::-1][:10]
            for test in before:
                if test not in audio_cache:
                    audio_cache[test] = np.asarray(read_audio(test), dtype=np.float64)
                offset = _locate(audio_cache[test], clip)
                if offset is None:
                    continue
                word = None if example.parent.name == "noise" else example.parent.name
                _add_truth(test, {"t": round(offset + 0.5, 2), "word": word, "example": key})
                found += 1
                break
    return found


def _locate(audio, clip, rate: int = 16000):
    """Où `clip` commence dans `audio` (secondes), s'il en est une copie ; sinon None."""
    import numpy as np

    if len(audio) < len(clip):
        return None
    n = 1 << int(np.ceil(np.log2(len(audio) + len(clip))))
    corr = np.fft.irfft(np.fft.rfft(audio, n) * np.conj(np.fft.rfft(clip, n)), n)[: len(audio) - len(clip) + 1]
    i = int(np.argmax(corr))
    window = audio[i : i + len(clip)]
    similarity = float(window @ clip) / (np.linalg.norm(window) * np.linalg.norm(clip) + 1e-12)
    return i / rate if similarity > 0.9 else None
