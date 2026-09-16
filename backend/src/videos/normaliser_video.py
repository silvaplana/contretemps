"""Corrige les métadonnées de couleur (VUI H.264) invalides que certains
téléphones écrivent dans leurs vidéos — vécu avec une vidéo prise sur un
Samsung Android ("Pokawa", signalée par l'utilisateur : "elle n'a pas de
vignette") : ffmpeg refusait de décoder la moindre frame ("Invalid color
range"), aussi bien pour la vignette (poster.py) que pour la compression
(compression.py), alors que le fichier n'est pas réellement corrompu — sa
durée, elle, se lit très bien (voir duree.py, qui ne décode jamais de
frame, juste les métadonnées du conteneur).

Corrigé par une COPIE DE FLUX (pas de ré-encodage, quasi instantané) qui
réécrit les paramètres VUI du flux H.264 avec des valeurs valides —
utilisé comme repli par poster.py/compression.py quand leur tentative
normale échoue, jamais en amont par précaution (la grande majorité des
vidéos n'ont pas ce problème, pas la peine de les remuxer toutes)."""

import subprocess
from pathlib import Path

import imageio_ffmpeg


def corriger_metadonnees_couleur(chemin_source, chemin_dest) -> bool:
    """`False` si la correction elle-même échoue (ex. flux qui n'est pas
    du H.264, le filtre `h264_metadata` ne s'applique qu'à ce codec) —
    l'appelant garde alors son échec d'origine, pas plus grave qu'avant."""
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    try:
        resultat = subprocess.run(
            [
                ffmpeg, "-y",
                "-i", str(chemin_source),
                "-c", "copy",
                "-bsf:v",
                "h264_metadata="
                "colour_primaries=1:transfer_characteristics=1:"
                "matrix_coefficients=1:video_full_range_flag=0",
                str(chemin_dest),
            ],
            capture_output=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return resultat.returncode == 0 and Path(chemin_dest).exists()
