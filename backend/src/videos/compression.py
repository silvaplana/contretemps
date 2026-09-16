"""Compression d'un fichier vidéo déjà reçu en entier — jamais avant/
pendant l'envoi (voir spec/SPEC.md §8 : pas d'encodeur matériel disponible
dans un navigateur, compresser en JS serait plus lent que l'upload
lui-même). Tâche de fond séparée (voir app/video_compression_worker.py),
après coup, sans jamais faire attendre l'utilisateur. Même binaire ffmpeg
embarqué que duree.py/poster.py (imageio_ffmpeg).
"""

import subprocess
from pathlib import Path

import imageio_ffmpeg

from .normaliser_video import corriger_metadonnees_couleur

# H.264 + AAC, largement compatibles (lecture native sur tous les
# navigateurs/téléphones visés, voir VideoThumb.jsx). CRF ("constant rate
# factor") : plus petit = meilleure qualité/plus gros fichier — 28 reste
# net sur un écran de téléphone pour une vidéo de répétition/chorégraphie,
# tout en réduisant nettement la taille. Hauteur plafonnée à 1080p : la
# résolution est ce qui pèse le plus, une répétition filmée au téléphone
# n'a pas besoin de 4K pour rester lisible.
CRF = 28
HAUTEUR_MAX = 1080


def _compresser_ffmpeg(chemin_source, chemin_dest) -> bool:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    try:
        resultat = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i", str(chemin_source),
                "-vf", f"scale=-2:'min({HAUTEUR_MAX},ih)'",
                "-c:v", "libx264",
                "-crf", str(CRF),
                "-preset", "veryfast",
                "-c:a", "aac",
                "-b:a", "128k",
                str(chemin_dest),
            ],
            capture_output=True,
            timeout=1800,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return resultat.returncode == 0 and Path(chemin_dest).exists()


def compresser(chemin_source: Path, chemin_dest: Path) -> bool:
    """`False` si ffmpeg échoue (fichier corrompu, format non reconnu...)
    — pas bloquant : voir le worker, qui garde alors le fichier d'origine
    tel quel plutôt que de le remplacer par un résultat manquant/corrompu.
    Timeout large (tâche de fond, personne n'attend le résultat).

    Un 1er échec retente une fois sur une copie aux métadonnées de
    couleur corrigées (voir normaliser_video.py — même souci vécu que
    pour la vignette, poster.py : certains téléphones Android écrivent
    des métadonnées invalides qu'un ffmpeg récent refuse de décoder)."""
    if _compresser_ffmpeg(chemin_source, chemin_dest):
        return True

    chemin_source = Path(chemin_source)
    chemin_corrige = chemin_source.with_name(f"{chemin_source.stem}-couleurs-tmp.mp4")
    try:
        if not corriger_metadonnees_couleur(chemin_source, chemin_corrige):
            return False
        return _compresser_ffmpeg(chemin_corrige, chemin_dest)
    finally:
        chemin_corrige.unlink(missing_ok=True)
