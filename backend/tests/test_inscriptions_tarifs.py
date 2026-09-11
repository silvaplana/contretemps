"""Tests de tarifs.py/saison.py — purs, sans DB (voir
spec/SPEC-inscription.md)."""

import datetime as dt

import pytest
from inscriptions.saison import saison_actuelle
from inscriptions.tarifs import (
    Echeance,
    calculer_echeances_helloasso,
    calculer_tarif,
    dates_trimestres,
    palier_par_defaut,
)


def test_palier_par_defaut_connait_les_17_cours():
    noms = [
        "Éveil", "Class Ini", "Jazz Ini", "Class Moy", "Jazz Moy", "Street Moyen",
        "Jazz Junior", "Street Junior Inter", "Class Inter", "Jazz Inter",
        "Pointes inter", "Pointes AV", "Class AV", "Jazz AV", "Contempo Junior",
        "Contempo Inter avance", "Contempo Adulte",
    ]
    for nom in noms:
        assert palier_par_defaut(nom) is not None, nom
    assert palier_par_defaut("Cours inconnu") is None


def test_eveil_tarif_fixe_quel_que_soit_le_nombre_de_cours():
    resultat = calculer_tarif(["Éveil"])
    assert resultat.palier == "eveil"
    assert resultat.montant_adhesion == 40.0
    assert resultat.montant_mensuel_septembre == 36.0
    assert resultat.montant_trimestriel == 110.0
    assert resultat.alerte_palier_mixte is False


def test_initiation_moyen_bareme_par_nombre_de_cours():
    assert calculer_tarif(["Class Ini"]).montant_mensuel_septembre == 42.0
    assert calculer_tarif(["Class Ini", "Jazz Ini"]).montant_mensuel_septembre == 50.0
    assert calculer_tarif(["Class Ini", "Jazz Ini", "Street Moyen"]).montant_mensuel_septembre == 55.0
    assert calculer_tarif(["Class Ini"]).montant_trimestriel == 125.0


def test_junior_et_plus_bareme_par_nombre_de_cours():
    resultat_1 = calculer_tarif(["Class Inter"])
    assert resultat_1.montant_mensuel_septembre == 42.0
    resultat_5 = calculer_tarif(
        ["Class Inter", "Jazz Inter", "Class AV", "Jazz AV", "Pointes AV"]
    )
    assert resultat_5.montant_mensuel_septembre == 72.0
    # Au-delà du barème connu (6 cours et plus) -> palier "illimité".
    resultat_illimite = calculer_tarif(
        ["Class Inter", "Jazz Inter", "Class AV", "Jazz AV", "Pointes AV", "Pointes inter"]
    )
    assert resultat_illimite.montant_mensuel_septembre == 75.0
    assert resultat_illimite.montant_trimestriel == 220.0


def test_contempo_adulte_rattache_au_palier_junior_et_plus():
    resultat = calculer_tarif(["Contempo Adulte"])
    assert resultat.palier == "junior_et_plus"
    assert resultat.montant_mensuel_septembre == 42.0


def test_palier_mixte_retient_le_plus_cher_et_alerte():
    resultat = calculer_tarif(["Éveil", "Class Inter"])
    assert resultat.palier == "junior_et_plus"
    assert resultat.alerte_palier_mixte is True

    resultat_non_mixte = calculer_tarif(["Class Ini", "Jazz Ini"])
    assert resultat_non_mixte.alerte_palier_mixte is False


def test_reduction_famille_appliquee():
    sans = calculer_tarif(["Class Ini"], reduction_famille=False)
    avec = calculer_tarif(["Class Ini"], reduction_famille=True)
    assert avec.montant_mensuel_septembre == sans.montant_mensuel_septembre - 5.0
    assert avec.montant_trimestriel == sans.montant_trimestriel - 5.0
    assert avec.reduction_famille_appliquee is True


def test_saison_actuelle_bascule_en_aout():
    assert saison_actuelle(dt.date(2026, 9, 11)) == "2026-2027"
    assert saison_actuelle(dt.date(2026, 8, 1)) == "2026-2027"
    assert saison_actuelle(dt.date(2026, 7, 31)) == "2025-2026"
    assert saison_actuelle(dt.date(2027, 1, 15)) == "2026-2027"


def test_dates_trimestres_saison():
    assert dates_trimestres("2026-2027") == [
        dt.date(2026, 10, 1),
        dt.date(2027, 1, 1),
        dt.date(2027, 4, 1),
    ]


def test_calculer_echeances_1x_paiement_unique():
    echeances = calculer_echeances_helloasso(40.0, 110.0, 1, "2026-2027")
    assert len(echeances) == 1
    assert echeances[0].montant == 40.0 + 110.0 * 3
    assert echeances[0].date_prelevement is None


def test_calculer_echeances_3x_inscription_avant_le_premier_trimestre():
    """Inscription en septembre, avant le début du 1er trimestre (voir
    dates_trimestres) : les 3 trimestres sont dans le futur, seule
    l'adhésion est payée immédiatement."""
    echeances = calculer_echeances_helloasso(
        40.0, 110.0, 3, "2026-2027", aujourdhui=dt.date(2026, 9, 11)
    )
    assert len(echeances) == 4
    assert echeances[0].montant == 40.0
    assert echeances[0].date_prelevement is None
    assert echeances[1] == Echeance(montant=110.0, date_prelevement=dt.date(2026, 10, 1))
    assert echeances[2] == Echeance(montant=110.0, date_prelevement=dt.date(2027, 1, 1))
    assert echeances[3] == Echeance(montant=110.0, date_prelevement=dt.date(2027, 4, 1))
    assert sum(e.montant for e in echeances) == 40.0 + 110.0 * 3


def test_calculer_echeances_3x_inscription_apres_le_debut_du_1er_trimestre():
    """Inscription en octobre (1er trimestre déjà entamé) : l'API
    HelloAsso refuserait une échéance dans le mois de l'échéance
    initiale — ce trimestre est donc payé immédiatement avec l'adhésion,
    seuls janvier et avril restent de vraies échéances futures."""
    echeances = calculer_echeances_helloasso(
        40.0, 110.0, 3, "2026-2027", aujourdhui=dt.date(2026, 10, 15)
    )
    assert len(echeances) == 3
    assert echeances[0].montant == 40.0 + 110.0
    assert echeances[0].date_prelevement is None
    assert echeances[1] == Echeance(montant=110.0, date_prelevement=dt.date(2027, 1, 1))
    assert echeances[2] == Echeance(montant=110.0, date_prelevement=dt.date(2027, 4, 1))


def test_calculer_echeances_3x_inscription_tardive_apres_avril():
    """Inscription en mai (les 3 trimestres sont déjà passés) : tout est
    payé immédiatement, aucune échéance future."""
    echeances = calculer_echeances_helloasso(
        40.0, 110.0, 3, "2026-2027", aujourdhui=dt.date(2027, 5, 2)
    )
    assert len(echeances) == 1
    assert echeances[0].montant == 40.0 + 110.0 * 3
    assert echeances[0].date_prelevement is None


def test_calculer_echeances_nb_invalide():
    with pytest.raises(ValueError):
        calculer_echeances_helloasso(40.0, 110.0, 2, "2026-2027")
