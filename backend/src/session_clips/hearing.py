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
# « Time » et « Go » dits en anglais, ou entendus comme des mots français.
WORDS = {
    "time": {"time", "times", "taim", "taime", "thaim", "thaime"},
    "go": {"go", "gos", "goo", "gow", "gau", "gaux"},
}

_model = None


def word_kind(word: str) -> str | None:
    """« time », « go » ou None."""
    plain = unicodedata.normalize("NFKD", word).encode("ascii", "ignore").decode().lower()
    plain = re.sub(r"[^a-z]", "", plain)
    return next((kind for kind, words in WORDS.items() if plain in words), None)


def is_time(word: str) -> bool:
    return word_kind(word) == "time"


def hear(video_path: Path) -> list[tuple[str, float]]:
    """Les « go » et « time » dits, avec leur moment en secondes. Si l'écoute échoue,
    aucun : les gestes suffisent, la vidéo est quand même lue (Seb, 12/11)."""
    try:
        return _hear(video_path)
    except Exception:
        print(f"Écoute impossible : {video_path.name}")
        traceback.print_exc()
        return []


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


def _hear(video_path: Path) -> list[tuple[str, float]]:
    global _model
    from faster_whisper import WhisperModel

    if _model is None:
        _model = WhisperModel(MODEL, device="cpu", compute_type="int8")
    segments, _ = _model.transcribe(
        _audio(video_path),
        word_timestamps=True,
        # En anglais : un « Go ! » seul, deviné dans une autre langue, sortait
        # en d'autres lettres (Seb, 12/11 : rien entendu dans « Go time »).
        language="en",
        # Ne transcrit que les passages où l'on parle, mais garde les cris
        # brefs (0,2 s) avec de la marge autour pour que Whisper les lise.
        vad_filter=True,
        vad_parameters={"threshold": 0.3, "min_speech_duration_ms": 50, "speech_pad_ms": 600},
        hotwords="Go, Time",
        condition_on_previous_text=False,
    )
    words = [w for s in segments for w in (s.words or [])]
    # Dans le journal de sparring-worker (action « Lire un essai du Labo ») :
    # ce que Whisper a compris, pour voir pourquoi un cri n'est pas compté.
    print(f"Entendu dans {video_path.name} : {' '.join(f'{w.word.strip()}@{w.start:.1f}' for w in words) or 'rien'}")
    return [(word_kind(w.word), round(w.start, 1)) for w in words if word_kind(w.word)]
