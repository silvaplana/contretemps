"""Écouter la bande son d'une vidéo : les « Time ! » criés par l'entraîneur
à la fin d'un combat (spec/modules/video-combats.md §5, Seb 12/11/2026).

Whisper (faster-whisper, modèle « base », sur le processeur) transcrit les
passages où quelqu'un parle, avec l'heure de chaque mot ; on garde les mots
qui sonnent comme « time ». Installé seulement dans le conteneur
`sparring-worker` (backend/Dockerfile.sparring), d'où l'import dans la
fonction, comme detector.py.
"""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path

MODEL = os.environ.get("SPARRING_SPEECH_MODEL", "base")
# « Time » dit en anglais, ou entendu comme un mot français.
WORDS = {"time", "times", "taim", "taime", "thaim", "thaime"}

_model = None


def is_time(word: str) -> bool:
    plain = unicodedata.normalize("NFKD", word).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]", "", plain) in WORDS


def hear(video_path: Path) -> list[float]:
    """Les moments (en secondes) où « Time ! » est dit."""
    global _model
    from faster_whisper import WhisperModel

    if _model is None:
        _model = WhisperModel(MODEL, device="cpu", compute_type="int8")
    segments, _ = _model.transcribe(
        str(video_path),
        word_timestamps=True,
        vad_filter=True,  # ne transcrit que les passages où l'on parle
        hotwords="Time",
        condition_on_previous_text=False,
    )
    return [round(w.start, 1) for s in segments for w in (s.words or []) if is_time(w.word)]
