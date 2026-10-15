"""Stockage protégé des contenus (spec §3.2, §4.1).

Les fichiers sont rangés sur le disque par organisation puis par empreinte
sha256 (`<racine>/<org>/ab/abcdef…`), et **jamais servis en statique** :
ils ne sortent que par les routes du module, après contrôle des droits
(receiver.py). Disque local pour commencer ; un stockage objet pourra
prendre la place de cette classe sans toucher au reste.
"""

from __future__ import annotations

import hashlib
import mimetypes
import os
import shutil
import tempfile
from pathlib import Path
from typing import BinaryIO

BLOC = 1024 * 1024


class FileTooLarge(Exception):
    def __init__(self, max_bytes: int) -> None:
        super().__init__(f"Fichier trop gros (maximum {max_bytes // (1024 * 1024)} Mo)")
        self.max_bytes = max_bytes


class LocalStorage:
    def __init__(self, root: Path, max_bytes: int) -> None:
        self.root = Path(root)
        self.max_bytes = max_bytes

    def path(self, org_id: int, sha256: str) -> Path:
        return self.root / str(org_id) / sha256[:2] / sha256

    def thumbnail_path(self, org_id: int, sha256: str) -> Path:
        return self.root / str(org_id) / "vignettes" / f"{sha256}.jpg"

    def put(self, org_id: int, source: BinaryIO) -> tuple[str, int]:
        """Copie `source` dans le stockage ; renvoie (sha256, taille).
        Écrit d'abord dans un fichier temporaire du même disque, puis le
        déplace : un envoi interrompu ne laisse jamais de fichier à moitié
        écrit sous son empreinte."""
        dossier = self.root / str(org_id)
        dossier.mkdir(parents=True, exist_ok=True)
        empreinte = hashlib.sha256()
        taille = 0
        descripteur, temporaire = tempfile.mkstemp(dir=dossier, prefix=".envoi-")
        try:
            with os.fdopen(descripteur, "wb") as sortie:
                while bloc := source.read(BLOC):
                    taille += len(bloc)
                    if taille > self.max_bytes:
                        raise FileTooLarge(self.max_bytes)
                    empreinte.update(bloc)
                    sortie.write(bloc)
            sha = empreinte.hexdigest()
            cible = self.path(org_id, sha)
            if cible.exists():
                os.unlink(temporaire)
            else:
                cible.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(temporaire, cible)
            return sha, taille
        except BaseException:
            if os.path.exists(temporaire):
                os.unlink(temporaire)
            raise

    def delete(self, org_id: int, sha256: str) -> None:
        for chemin in (self.path(org_id, sha256), self.thumbnail_path(org_id, sha256)):
            try:
                chemin.unlink()
            except FileNotFoundError:
                pass

    def usage(self, org_id: int) -> int:
        dossier = self.root / str(org_id)
        if not dossier.exists():
            return 0
        return sum(f.stat().st_size for f in dossier.rglob("*") if f.is_file())


def guess_mime(filename: str) -> str:
    mime, _ = mimetypes.guess_type(filename)
    return mime or "application/octet-stream"


def make_thumbnail(source: Path, target: Path, size: int = 320) -> bool:
    """Vignette JPEG d'une image (Pillow). False si ce n'est pas une image
    lisible : l'appli affiche alors l'icône du type."""
    try:
        from PIL import Image, ImageOps

        with Image.open(source) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail((size, size))
            if image.mode not in ("RGB", "L"):
                fond = Image.new("RGB", image.size, (255, 255, 255))
                fond.paste(image, mask=image.convert("RGBA").split()[-1])
                image = fond
            target.parent.mkdir(parents=True, exist_ok=True)
            image.save(target, "JPEG", quality=80)
        return True
    except Exception:
        return False
