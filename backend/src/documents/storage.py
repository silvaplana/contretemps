"""Le stockage vit désormais dans le core (`storage/`), partagé avec la
messagerie ; ce nom reste pour les imports du module."""

from storage import FileTooLarge, LocalStorage, guess_mime, make_thumbnail

__all__ = ["FileTooLarge", "LocalStorage", "guess_mime", "make_thumbnail"]
