"""Where the news module keeps its photos (spec/modules/actualites.md §3.3):
a folder of its own next to the videos one, one sub-folder per organization.
Each photo is kept as sent, plus a JPEG of at most 1600 px, the one shown."""

import os
from pathlib import Path

from storage import LocalStorage
from videos.stockage import DOSSIER_VIDEOS_LIVE

DOSSIER_ACTUALITES = Path(os.environ.get("NEWS_DIR", DOSSIER_VIDEOS_LIVE.parent / "actualites"))
PHOTO_MAX_BYTES = 25 * 1024 * 1024
DISPLAY_SIZE = 1600


def news_storage() -> LocalStorage:
    return LocalStorage(DOSSIER_ACTUALITES, PHOTO_MAX_BYTES)
