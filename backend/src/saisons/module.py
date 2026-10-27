"""Déclaration du module Saisons (spec/modules/saisons.md) : créer, modifier,
supprimer et consulter les saisons. Éteint, l'école reste sur sa période
(la dernière saison) : routes introuvables, en-tête X-Saison-Id ignoré
(comptes/rbac.py)."""

from registry import Module

from .receiver import SaisonsReceiver

KEY = "seasons"


def mount(app, core) -> None:
    SaisonsReceiver(client=core.gestion_saisons, app=app)


MODULE = Module(key=KEY, label="Saisons", mount=mount)
