"""Convention de stockage des fichiers générés par une inscription (PDF
dossier/facture, Excel "nouvelles inscriptions") — même patron que
`videos/stockage.py` : un dossier par école, configurable via env
(`INSCRIPTIONS_DIR`), jamais commité (voir .gitignore : `/data/`).
"""

import os
from pathlib import Path

DOSSIER_INSCRIPTIONS = Path(os.environ.get("INSCRIPTIONS_DIR", "./data/inscriptions"))


def dossier_ecole(ecole_id: int) -> Path:
    """Crée le dossier de l'école si besoin et le renvoie."""
    dossier = DOSSIER_INSCRIPTIONS / str(ecole_id)
    dossier.mkdir(parents=True, exist_ok=True)
    return dossier


def chemin_relatif(ecole_id: int, nom_fichier: str) -> str:
    """Valeur à stocker en base (`pdf_dossier_chemin`/`pdf_facture_chemin`)
    — voir dossier_ecole."""
    return f"{ecole_id}/{nom_fichier}"
