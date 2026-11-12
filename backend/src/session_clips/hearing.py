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


def _hear(video_path: Path) -> list[tuple[str, float]]:
    global _model
    from faster_whisper import WhisperModel

    if _model is None:
        _model = WhisperModel(MODEL, device="cpu", compute_type="int8")
    segments, _ = _model.transcribe(
        str(video_path),
        word_timestamps=True,
        vad_filter=True,  # ne transcrit que les passages où l'on parle
        hotwords="Go, Time",
        condition_on_previous_text=False,
    )
    words = [w for s in segments for w in (s.words or [])]
    return [(word_kind(w.word), round(w.start, 1)) for w in words if word_kind(w.word)]
