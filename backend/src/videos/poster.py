"""Vignette (poster) générée depuis un fichier vidéo — même binaire
ffmpeg embarqué que duree.py (imageio_ffmpeg, pas de dépendance système).
Utilisée par le vrai upload (voir videos.py : creer_avec_upload) — avant,
les 2 vignettes de démo avaient été générées une fois à la main avec la
même commande (voir backend/videos_reference/, committé).
"""

import subprocess
from pathlib import Path

import imageio_ffmpeg


def generer_poster(chemin_video, chemin_poster) -> bool:
    """Extrait une image représentative et l'enregistre en .jpg, largeur
    464px (même convention que les vignettes de démo) — le filtre
    "thumbnail" choisit une frame représentative sans avoir besoin de
    connaître la durée au préalable (contrairement à "chercher à la
    1re seconde", qui échouerait sur un clip plus court). `False` si
    ffmpeg échoue (fichier corrompu, format non reconnu...) — pas
    bloquant, juste pas de poster pour cette vidéo."""
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    try:
        resultat = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i", str(chemin_video),
                "-vf", "thumbnail,scale=464:-1",
                "-frames:v", "1",
                str(chemin_poster),
            ],
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return resultat.returncode == 0 and Path(chemin_poster).exists()
