"""Durée d'un fichier vidéo, en secondes — via le binaire ffmpeg embarqué
par `imageio_ffmpeg` (pas de dépendance système, portable comme les autres
libs du projet). Sert au seed de démo (durée réelle des vidéos de
référence) et sera repris par le vrai upload (chantier suivant).
"""

import re
import subprocess

import imageio_ffmpeg

_RE_DUREE = re.compile(r"Duration:\s*(\d+):(\d{2}):(\d{2})\.(\d+)")


def duree_secondes(chemin) -> int | None:
    """`chemin` : `Path` ou `str` vers un fichier vidéo existant. `None` si
    la durée n'a pas pu être lue (fichier absent/corrompu) — ffmpeg écrit
    ses infos sur stderr même sans fichier de sortie (juste "-i", pas de
    conversion), donc pas besoin de décoder le flux vidéo entier."""
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    try:
        resultat = subprocess.run(
            [ffmpeg, "-i", str(chemin)],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    m = _RE_DUREE.search(resultat.stderr)
    if not m:
        return None
    heures, minutes, secondes, _centiemes = m.groups()
    return int(heures) * 3600 + int(minutes) * 60 + int(secondes)
