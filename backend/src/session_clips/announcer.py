"""L'annonce du vainqueur au Timer étendu (Seb, 21/11 ; spec §6.5 ter) : le nom
du vainqueur dit par « George », la voix d'annonceur choisie par Seb, avec
l'écho d'une grande salle. Le début (« And the winner, by unanimous decision,
is… »), le match nul et la foule sont des fichiers fixes du Timer ; seul le
nom est fabriqué ici, une fois par personne, puis gardé dans le dossier de
l'école (`<VIDEOS_DIR>/<école>/announce/<personne>-<empreinte>.mp3`).

La voix : Kokoro (kokoro-onnx, hors ligne, voix `bm_george`). Le modèle
(environ 350 Mo) est téléchargé à la première annonce dans `KOKORO_DIR`
(volume persistant), comme le détourage du logo."""

from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import threading
import urllib.request
import wave
from pathlib import Path

from videos.stockage import dossier_ecole

MODEL_DIR = Path(os.environ.get("KOKORO_DIR", "./data/kokoro"))
RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
FILES = ("kokoro-v1.0.onnx", "voices-v1.0.bin")
VOICE, LANG, SPEED = "bm_george", "en-gb", 0.7
# Un demi-ton plus grave, l'écho d'une grande salle, le volume des autres sons du Timer.
EFFECTS = "asetrate=24000*0.9439,aresample=24000,atempo=1.0594,aecho=0.8:0.6:70|140|260:0.35|0.25|0.15,loudnorm=I=-14:TP=-1"

_lock = threading.Lock()
_kokoro = None


class VoiceUnavailable(Exception):
    """La voix ne peut pas parler sur ce serveur (paquet ou modèle absent)."""


def _model():
    global _kokoro
    if _kokoro is None:
        try:
            from kokoro_onnx import Kokoro
        except ImportError as e:
            raise VoiceUnavailable("Voix indisponible") from e
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        for name in FILES:
            target = MODEL_DIR / name
            if not target.exists():
                part = target.with_suffix(".part")
                urllib.request.urlretrieve(RELEASE + name, part)
                part.rename(target)
        _kokoro = Kokoro(str(MODEL_DIR / FILES[0]), str(MODEL_DIR / FILES[1]))
    return _kokoro


def speak(text: str, target: Path) -> None:
    """Le texte dit par George, en mp3, avec les effets."""
    import imageio_ffmpeg
    import numpy as np

    with _lock:  # un seul modèle en mémoire, une phrase à la fois
        samples, rate = _model().create(text, voice=VOICE, speed=SPEED, lang=LANG)
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes()
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "voix.wav"
        with wave.open(str(raw), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(pcm)
        part = target.with_suffix(".part.mp3")
        subprocess.run(
            [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(raw), "-af", EFFECTS,
             "-ar", "44100", "-b:a", "96k", str(part)],
            check=True,
        )
        part.replace(target)


def name_file(org_id: int, person_id: int, full_name: str) -> Path:
    """Le nom annoncé, fabriqué au premier appel. L'empreinte du nom change le
    fichier si la fiche est renommée."""
    digest = hashlib.sha1(full_name.encode()).hexdigest()[:10]
    folder = dossier_ecole(org_id) / "announce"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{person_id}-{digest}.mp3"
    if not target.exists():
        speak(f"{full_name}!", target)
    return target
