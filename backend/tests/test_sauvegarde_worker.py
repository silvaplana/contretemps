"""Tests de la logique "est-ce dû maintenant ?" du worker de sauvegarde
programmée (voir app/sauvegarde_worker.py) — pas le worker lui-même
(boucle infinie, jamais exécutée en test)."""

import datetime as dt

from app.sauvegarde_worker import _est_due
from ecoles.models import Ecole


def _ecole(**overrides):
    defaut = dict(
        id=1, nom="Test", code_postal="83330",
        code_acces_admin="A", code_acces_prof="P", code_acces_eleve="E",
        sauvegarde_active=True, sauvegarde_periodicite="jour",
        sauvegarde_jour_semaine=None, sauvegarde_heure="03:00",
        sauvegarde_derniere_execution=None,
    )
    defaut.update(overrides)
    return Ecole(**defaut)


def test_inactive_jamais_due():
    ecole = _ecole(sauvegarde_active=False)
    assert _est_due(ecole, dt.datetime(2026, 9, 16, 3, 0)) is False


def test_quotidienne_due_a_la_bonne_heure():
    ecole = _ecole(sauvegarde_periodicite="jour", sauvegarde_heure="03:00")
    assert _est_due(ecole, dt.datetime(2026, 9, 16, 3, 0)) is True
    assert _est_due(ecole, dt.datetime(2026, 9, 16, 3, 1)) is False


def test_quotidienne_pas_2_fois_le_meme_jour():
    ecole = _ecole(
        sauvegarde_periodicite="jour", sauvegarde_heure="03:00",
        sauvegarde_derniere_execution=dt.datetime(2026, 9, 16, 3, 0),
    )
    assert _est_due(ecole, dt.datetime(2026, 9, 16, 3, 0)) is False
    assert _est_due(ecole, dt.datetime(2026, 9, 17, 3, 0)) is True


def test_hebdomadaire_seulement_le_bon_jour():
    # 2026-09-16 est un mercredi (weekday()==2).
    ecole = _ecole(sauvegarde_periodicite="semaine", sauvegarde_jour_semaine=2, sauvegarde_heure="03:00")
    assert _est_due(ecole, dt.datetime(2026, 9, 16, 3, 0)) is True
    assert _est_due(ecole, dt.datetime(2026, 9, 17, 3, 0)) is False


def test_mensuelle_seulement_le_1er():
    ecole = _ecole(sauvegarde_periodicite="mois", sauvegarde_heure="03:00")
    assert _est_due(ecole, dt.datetime(2026, 10, 1, 3, 0)) is True
    assert _est_due(ecole, dt.datetime(2026, 10, 2, 3, 0)) is False


def test_sans_heure_configuree_jamais_due():
    ecole = _ecole(sauvegarde_heure=None)
    assert _est_due(ecole, dt.datetime(2026, 9, 16, 3, 0)) is False
