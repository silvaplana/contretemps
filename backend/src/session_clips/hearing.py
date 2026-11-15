"""Écouter la bande son d'une vidéo : les « Go ! » criés par l'entraîneur au
début d'un combat et les « Time ! » à la fin (spec/modules/video-combats.md
§5, Seb 12/11/2026).

Whisper (faster-whisper, modèle « base », sur le processeur) transcrit les
passages où quelqu'un parle, avec l'heure de chaque mot ; on garde les mots
qui sonnent comme « go » ou « time ». Installé seulement dans le conteneur
`sparring-worker` (backend/Dockerfile.sparring), d'où l'import dans la
fonction, comme detector.py.
"""

from __future__ import annotations

import os
import re
import subprocess
import traceback
import unicodedata
from pathlib import Path

MODEL = os.environ.get("SPARRING_SPEECH_MODEL", "base")
# Deux écoutes au choix dans les réglages (Seb, 14/11) : « base » (rapide) et
# « small » (plus précise, environ 3 fois plus lente), téléchargées dans l'image.
# « club » : l'écoute du club (club_hearing.py), comparée aux cris enregistrés (Seb, 14/11).
SPEECH_MODELS = ("base", "small", "club")
MODELS_DIR = os.environ.get("SPARRING_SPEECH_DIR", "")
# « Time » et « Go » dits en anglais, ou entendus comme des mots français.
WORDS = {
    "time": {"time", "times", "taim", "taime", "thaim", "thaime"},
    "go": {"go", "gos", "goo", "gow", "gau", "gaux"},
    # « Combattez ! » (Seb, 15/11, à la place de « Combat ! ») : Whisper, en anglais, l'écrit de plusieurs façons.
    "combattez": {"combattez", "combatez", "combattes", "combates", "combattay", "combatay", "combate", "combatte", "combatté", "combattee"},
}

_models: dict = {}


def _model_path(name: str) -> str:
    if name == "base":
        return MODEL
    folder = Path(MODELS_DIR) / f"whisper-{name}" if MODELS_DIR else None
    return str(folder) if folder and folder.exists() else name


def word_kind(word: str) -> str | None:
    """« time », « go », « combattez » ou None (« hajime » retiré le 15/11)."""
    plain = unicodedata.normalize("NFKD", word).encode("ascii", "ignore").decode().lower()
    plain = re.sub(r"[^a-z]", "", plain)
    return next((kind for kind, words in WORDS.items() if plain in words), None)


def is_time(word: str) -> bool:
    return word_kind(word) == "time"


def hear(video_path: Path, model: str = "base") -> list[tuple[str, float, float, float]]:
    """Les cris dits : (mot, moment en secondes, note de confiance, volume en dB
    au-dessus du bruit de fond ; Seb 14/11, contre les mots inventés). Si l'écoute échoue,
    aucun : les gestes suffisent, la vidéo est quand même lue (Seb, 12/11)."""
    try:
        return _hear_club(video_path) if model == "club" else _hear(video_path, model)
    except Exception:
        print(f"Écoute impossible : {video_path.name}")
        traceback.print_exc()
        return []


def hear_timer(video_path: Path) -> list[tuple[str, float, float, float]]:
    """La cloche (« bell ») et les trois coups (« bells ») du Timer de Fights
    (timer_bells.py, Seb 14/11), au format des cris ; aucun si la lecture échoue."""
    try:
        from .timer_bells import bells

        found = bells(_audio(video_path))
    except Exception:
        print(f"Sons du Timer illisibles : {video_path.name}")
        traceback.print_exc()
        return []
    if found:
        print(f"Timer dans {video_path.name} : " + " ".join(f"{k}@{t:.1f}~{s:.2f}" for k, t, s, _db in found))
    return found


def hear_club_without(video_path: Path, exclude: frozenset[str]) -> list[tuple[str, float, float, float, float]]:
    """L'écoute du club sans certains exemples (« Rejouer tous les essais »,
    voice.run_replays), avant le seuil : (mot, moment, ressemblance, avance
    sur le 2e, volume) ; le rejeu règle le seuil. Aucun cri si elle échoue."""
    try:
        return _hear_club(video_path, exclude, raw=True)
    except Exception:
        print(f"Écoute impossible : {video_path.name}")
        traceback.print_exc()
        return []


def voice_dir(video_path: Path) -> Path:
    """Les cris enregistrés de l'école de la vidéo : les vidéos sont rangées
    dans `<VIDEOS_DIR>/<école>/…` et les cris dans `<VIDEOS_DIR>/<école>/voice/`."""
    from videos.stockage import DOSSIER_VIDEOS_LIVE

    school = video_path.resolve().relative_to(DOSSIER_VIDEOS_LIVE.resolve()).parts[0]
    return DOSSIER_VIDEOS_LIVE / school / "voice"


def _hear_club(video_path: Path, exclude: frozenset[str] = frozenset(), raw: bool = False) -> list:
    import json

    from .club_hearing import candidates, pick_with_near, templates

    folder = voice_dir(video_path)
    words = templates(folder, _audio, exclude)
    found = candidates(_audio(video_path), words)
    if raw:
        return found
    # Le seuil et l'écart réglés par le dernier « Rejouer tous les essais » (voice.py).
    tuned = folder.parent / "voice-replays" / "thresholds.json"
    limits = json.loads(tuned.read_text()) if tuned.exists() else {}
    kept = pick_with_near(found, **limits)
    print(
        f"Écoute du club dans {video_path.name} ({', '.join(f'{w} ×{len(e)}' for w, e in words.items()) or 'aucun cri enregistré'}"
        f"{', seuil ' + str(limits) if limits else ''}) : "
        + (" ".join(f"{k}@{t:.1f}~{s:.2f}/{m:.2f}" for k, t, s, m, _db in found) or "rien")
        + f" → {sum(len(x) == 4 for x in kept)} gardés, {sum(len(x) == 5 for x in kept)} presque"
    )
    return kept


def _audio(video_path: Path):
    """Le son en 16 kHz mono, lu par ffmpeg : le décodeur de faster-whisper
    (PyAV) ne marchait pas dans l'image (« open() got an unexpected keyword
    argument 'metadata_errors' », 12/11), et aucun son n'était jamais entendu."""
    import imageio_ffmpeg
    import numpy as np

    raw = subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-nostdin", "-loglevel", "error", "-i", str(video_path),
         "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
        capture_output=True,
        check=True,
    ).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0


def _hear(video_path: Path, model: str = "base") -> list[tuple[str, float]]:
    from faster_whisper import WhisperModel

    if model not in _models:
        _models[model] = WhisperModel(_model_path(model), device="cpu", compute_type="int8")
    audio = _audio(video_path)
    segments, _ = _models[model].transcribe(
        audio,
        word_timestamps=True,
        # En anglais : un « Go ! » seul, deviné dans une autre langue, sortait
        # en d'autres lettres (Seb, 12/11 : rien entendu dans « Go time »).
        language="en",
        # Ne transcrit que les passages où l'on parle, mais garde les cris
        # brefs (0,2 s) avec de la marge autour pour que Whisper les lise.
        vad_filter=True,
        vad_parameters={"threshold": 0.3, "min_speech_duration_ms": 50, "speech_pad_ms": 600},
        hotwords="Go, Combattez, Time",
        condition_on_previous_text=False,
    )
    words = [w for s in segments for w in (s.words or [])]
    # Dans le journal de sparring-worker (action « Lire un essai du Labo ») :
    # ce que Whisper a compris, pour voir pourquoi un cri n'est pas compté.
    print(
        f"Entendu dans {video_path.name} : "
        + (" ".join(f"{w.word.strip()}@{w.start:.1f}~{w.probability:.2f}" for w in words) or "rien")
    )
    volumes = loudness(audio)
    return [
        (kind, start, round(float(w.probability), 2), _peak(volumes, w.start, w.end))
        for (kind, start), w in heard_words([(w.word, w.start) for w in words], with_words=words)
    ]


FRAME = 0.05  # secondes


BACKGROUND_SPAN = 10.0  # secondes : le bruit de fond est celui d'autour, pas de toute la vidéo


def loudness(audio) -> list[float]:
    """Le volume (dB) de chaque tranche de 50 ms, moins le bruit de fond
    d'autour (le 20e centile des 10 s autour ; étude du 14/11 : la médiane
    de tout l'enregistrement faisait d'un passage bruyant une suite de
    cris) : 0 dB sur un passage calme, beaucoup plus sur un cri."""
    import numpy as np

    n = int(16000 * FRAME)
    if len(audio) < n:
        return []
    frames = audio[: len(audio) // n * n].reshape(-1, n)
    db = 20 * np.log10(np.sqrt((frames**2).mean(axis=1)) + 1e-6)
    half = int(BACKGROUND_SPAN / FRAME / 2)
    if len(db) <= 2 * half:
        return [float(x) for x in db - float(np.percentile(db, 20))]
    windows = np.lib.stride_tricks.sliding_window_view(np.pad(db, half, mode="edge"), 2 * half + 1)
    return [float(x) for x in db - np.percentile(windows, 20, axis=1)]


def _peak(volumes: list[float], start: float, end: float) -> float:
    """Le plus fort du mot, avec 0,5 s de marge après (l'écoute place souvent
    le mot un peu tôt)."""
    a, b = int(start / FRAME), int((end + 0.5) / FRAME) + 1
    part = volumes[max(a, 0) : b]
    return round(float(max(part)), 1) if part else 0.0  # pas un float32 de numpy : il va dans du JSON


def heard_words(words: list[tuple[str, float]], with_words: list | None = None) -> list:
    """Les cris reconnus, mot par mot ; un mot coupé en deux (« Combat tez »)
    est recollé avec le suivant. Avec `with_words`, chaque cri vient avec
    son mot de Whisper (pour sa note et son volume)."""
    out, skip = [], False
    for i, (word, start) in enumerate(words):
        if skip:
            skip = False
            continue
        kind = word_kind(word)
        if kind is None and i + 1 < len(words):
            kind = word_kind(word + words[i + 1][0])
            skip = kind is not None
        if kind:
            out.append(((kind, round(start, 1)), with_words[i]) if with_words is not None else (kind, round(start, 1)))
    return out
