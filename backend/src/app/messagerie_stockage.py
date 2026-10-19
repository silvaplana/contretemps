"""Où la messagerie range ses photos, vidéos et fichiers
(spec/modules/messagerie-instantanee.md §4.4) : un dossier à part, à côté de
celui des vidéos de chorégraphie. Partagé par app.main et le worker de
compression vidéo (qui ne doit jamais importer app.main).
"""

import os
from pathlib import Path

from messagerie import Attachments
from storage import LocalStorage
from videos.stockage import DOSSIER_VIDEOS_LIVE

DOSSIER_MESSAGERIE = Path(os.environ.get("MESSAGERIE_DIR", DOSSIER_VIDEOS_LIVE.parent / "messagerie"))
TAILLE_MAX_PIECE_JOINTE = 25 * 1024 * 1024


def pieces_jointes() -> Attachments:
    return Attachments(LocalStorage(DOSSIER_MESSAGERIE, TAILLE_MAX_PIECE_JOINTE))
