"""Importation automatique de pièces (spec/modules/import-auto-pieces.md) : des fichiers
qui arrivent dans un dossier du club deviennent des pièces de Financier ›
Pièces, À valider."""

from .models import AutoImportRule, AutoImportSeen

__all__ = ["AutoImportRule", "AutoImportSeen"]
