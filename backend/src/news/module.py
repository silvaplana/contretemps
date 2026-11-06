"""Déclaration du module Actualités. Pour l'instant, seulement son droit
« 🔒 Publier les actualités » (spec/core.md §5.3), coché comme « Accès au
Financier » dans Admin > École > Administrateurs. La page viendra ensuite."""

from registry import Module, Right

PUBLISH = "news.publish"


def mount(app, core) -> None:
    pass


MODULE = Module(key="news", label="Actualités", mount=mount, rights=(Right(PUBLISH, "Publier les actualités"),))
