"""Enregistrement des modules (spec/core.md §9 bis)."""

import pytest

import registry
from app.modules import MODULES
from registry import Module


def _module(key, requires=()):
    return Module(key=key, label=key, mount=lambda app, core: None, requires=requires)


def test_la_liste_de_contretemps_est_valide():
    registry.check(MODULES)


def test_un_module_doit_venir_apres_ceux_dont_il_a_besoin():
    with pytest.raises(RuntimeError, match="documents"):
        registry.check([_module("expense_notes", requires=("documents",)), _module("documents")])
    registry.check([_module("documents"), _module("expense_notes", requires=("documents",))])


def test_un_module_ne_se_liste_qu_une_fois():
    with pytest.raises(RuntimeError, match="deux fois"):
        registry.check([_module("videos"), _module("videos")])


def test_l_assistant_recoit_les_actions_des_modules():
    from app import main

    noms = set(main.assistant_client.actions.by_name)
    attendus = {action.name for action in registry.actions(MODULES, main.core)}
    assert attendus and attendus <= noms
