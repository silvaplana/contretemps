"""Convention de stockage des fichiers vidéo eux-mêmes (voir spec/SPEC.md
§6.8) : un DOSSIER PAR ÉCOLE, pour ne jamais mélanger les fichiers de
deux écoles différentes — cohérent avec `ecole_id` déjà présent sur
(quasiment) toutes les tables du projet.

Les fichiers du dossier "live" ne sont JAMAIS commités dans git (voir
.gitignore) — seul `videos.lien_fichier` (le chemin RELATIF, ex.
"3/repetition.mp4") est en base ; ce module calcule où ce chemin pointe
réellement sur le disque, et sert de repère unique pour ce calcul (pas
dupliqué ailleurs). Le dossier "référence" (voir DOSSIER_VIDEOS_REFERENCE
ci-dessous), lui, EST commité (backend/videos_reference/) : un petit jeu
de démo curaté, figé dans l'image Docker (voir Dockerfile), pas des
uploads arbitraires.
"""

import os
from pathlib import Path

# Dossier "live" réellement servi par l'appli (voir app/main.py, monté en
# statique sous /media/videos). Vide par défaut — rempli par les uploads,
# ou par reset_demo.py qui le recopie depuis DOSSIER_VIDEOS_REFERENCE.
DOSSIER_VIDEOS_LIVE = Path(os.environ.get("VIDEOS_DIR", "./uploads/videos"))

# Dossier de référence, séparé du dossier "live" : contient un jeu de
# vidéos de démo connu et stable. reset_demo.py écrase le dossier "live"
# avec une copie de celui-ci, pour repartir d'un état propre après des
# tests qui ont ajouté/modifié des fichiers en local ou sur le VPS.
DOSSIER_VIDEOS_REFERENCE = Path(os.environ.get("VIDEOS_REFERENCE_DIR", "./videos_reference"))


def dossier_ecole(ecole_id: int) -> Path:
    """Crée le dossier de l'école si besoin et le renvoie."""
    dossier = DOSSIER_VIDEOS_LIVE / str(ecole_id)
    dossier.mkdir(parents=True, exist_ok=True)
    return dossier


def chemin_relatif(ecole_id: int, nom_fichier: str) -> str:
    """Valeur à stocker dans `videos.lien_fichier` — voir dossier_ecole."""
    return f"{ecole_id}/{nom_fichier}"
