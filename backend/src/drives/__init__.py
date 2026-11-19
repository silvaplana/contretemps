"""Drives du club (spec/core.md §3, « Drives du club ») : les kDrive et
Google Drive d'une organisation, connectés dans Admin › École › Connexions
comme les boîtes mail. Une ressource de l'école que plusieurs modules lisent
(premier : Import auto pièces, spec/modules/import-auto-pieces.md)."""

from .models import DriveAccount

__all__ = ["DriveAccount"]
