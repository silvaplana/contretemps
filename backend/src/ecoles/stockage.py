"""Convention de stockage des sauvegardes générées côté serveur
("Programmer sauvegarde École", voir sauvegarde_worker.py) — même patron
que `inscriptions/stockage.py`/`videos/stockage.py` : un dossier par
école, configurable via env (`SAUVEGARDES_DIR`), jamais commité (voir
.gitignore : `/data/`).

Filet de sécurité UNIQUEMENT (voir la conversation utilisateur) : la vraie
sauvegarde "voulue" par l'utilisateur atterrit sur SON disque local, via
le navigateur (voir frontend/src/api/sauvegarde.js) — ce dossier serveur
garantit juste que rien n'est perdu même si personne n'a l'appli ouverte
au moment programmé.
"""

import os
from pathlib import Path

DOSSIER_SAUVEGARDES = Path(os.environ.get("SAUVEGARDES_DIR", "./data/sauvegardes"))


def dossier_ecole(ecole_id: int) -> Path:
    """Crée le dossier de l'école si besoin et le renvoie."""
    dossier = DOSSIER_SAUVEGARDES / str(ecole_id)
    dossier.mkdir(parents=True, exist_ok=True)
    return dossier
