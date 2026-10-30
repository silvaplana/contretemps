"""Le Financier ouvert à l'assistant (finances_contretemps/lectures.py,
notes_frais_contretemps/actions.py ; Seb, 30 octobre) : lectures sans carte,
écritures par carte Faire / Annuler, réservées aux trésoriers."""

# ruff: noqa: F811 (fixture `ecole` importée)
import datetime as dt
import json

import pytest
from test_finances_actions import _faire, _proposer, ecole  # noqa: F401

from app import main
from documents_contretemps.adapter import personne_id
from notes_frais.ports import Membre

pytestmark = pytest.mark.rbac_reel

actions = main.assistant_client.actions


def _lire(db, compte, ecole, nom, args=None):
    texte, carte = _proposer(db, compte, ecole, nom, args or {})
    assert carte is None, texte
    return json.loads(texte)


def test_lectures_reservees_aux_tresoriers(db_session, ecole):
    texte, carte = _proposer(db_session, ecole["admin"], ecole, "finance_bank_accounts", {})
    assert carte is None and "trésoriers" in texte
    texte, carte = _proposer(db_session, ecole["admin"], ecole, "expense_notes", {})
    assert carte is None and "trésoriers" in texte


def test_comptes_lignes_et_plan(db_session, ecole):
    t = ecole["tresorier"]
    comptes = _lire(db_session, t, ecole, "finance_bank_accounts")
    assert comptes["total"] > 0 and comptes["withoutAccount"] > 0
    lignes = _lire(db_session, t, ecole, "finance_operations", {"text": "pizza"})
    assert lignes["count"] == 1 and lignes["lines"][0]["amount"] == -186.8 and lignes["lines"][0]["planAccount"] is None
    plan = _lire(db_session, t, ecole, "finance_chart")
    assert any(a["nature"] == "depense" for a in plan["accounts"])


def test_confirmer_le_compte_de_lignes_par_libelle(db_session, ecole):
    t = ecole["tresorier"]
    depense = next(a for a in _lire(db_session, t, ecole, "finance_chart")["accounts"] if a["nature"] == "depense")
    texte, carte = _proposer(db_session, t, ecole, "set_operation_accounts", {"text": "PIZZA", "plan_account": depense["number"]})
    assert carte is not None and "1 ligne" in carte["lignes"][0] and depense["number"] in carte["lignes"][0]
    assert _faire(db_session, t, ecole, carte)[0]["ok"]
    lignes = _lire(db_session, t, ecole, "finance_operations", {"plan_account": depense["number"]})
    assert lignes["count"] == 1 and lignes["lines"][0]["label"].startswith("VIR PIZZA")
    # Plus rien sans compte avec ce libellé.
    texte, carte = _proposer(db_session, t, ecole, "set_operation_accounts", {"text": "PIZZA", "plan_account": depense["number"]})
    assert carte is None and "aucune ligne" in texte


def test_bilan_documents_et_rapport_lisibles(db_session, ecole):
    t, saison = ecole["tresorier"], ecole["saison"]
    texte, carte = _proposer(db_session, t, ecole, "produce_financial_report", {})
    assert _faire(db_session, t, ecole, carte)[0]["ok"]
    bilans = _lire(db_session, t, ecole, "finance_reports")["reports"]
    assert len(bilans) == 1 and bilans[0]["hasResult"]
    bilan = _lire(db_session, t, ecole, "finance_report", {"report_id": bilans[0]["id"]})
    assert bilan["result"]["totalIncome"] is not None and bilan["financialStatement"] is None
    synthese = _lire(db_session, t, ecole, "finance_ag_document", {"document": "synthese"})
    assert synthese["season"] == saison.name and "unclassified" in synthese
    texte, carte = _proposer(db_session, t, ecole, "finance_ag_document", {"document": "balance"})
    assert carte is None and "Complet" in texte
    texte, carte = _proposer(db_session, t, ecole, "recalculate_financial_report", {"report_id": bilans[0]["id"]})
    assert carte is not None and _faire(db_session, t, ecole, carte)[0]["ok"]
    texte, carte = _proposer(db_session, t, ecole, "finance_report", {"report_id": 999})
    assert carte is None and "introuvable" in texte


def test_ajouter_puis_renommer_un_compte_du_plan(db_session, ecole):
    t = ecole["tresorier"]
    texte, carte = _proposer(db_session, t, ecole, "edit_chart_account", {"number": "6137", "label": "Location salle"})
    assert carte is None and "nature" in texte
    texte, carte = _proposer(db_session, t, ecole, "edit_chart_account",
                             {"number": "6137", "label": "Location salle", "nature": "depense", "keywords": ["GALLI"]})
    assert carte is not None and "Ajouter" in carte["lignes"][0]
    assert _faire(db_session, t, ecole, carte)[0]["ok"]
    texte, carte = _proposer(db_session, t, ecole, "edit_chart_account", {"number": "6137", "label": "Location Galli"})
    assert carte is not None and "Renommer" in carte["lignes"][0]
    assert _faire(db_session, t, ecole, carte)[0]["ok"]
    compte = next(a for a in _lire(db_session, t, ecole, "finance_chart")["accounts"] if a["number"] == "6137")
    assert compte["label"] == "Location Galli" and compte["keywords"] == ["GALLI"]


def test_proposer_des_validations_de_pieces(db_session, ecole):
    t = ecole["tresorier"]
    membre = Membre(person_id=personne_id(db_session, t), org_id=ecole["id"], nom="Julia Dho", emails=[], est_tresorier=True)
    service = main.notes_frais_client
    achats = [
        service.etablir(db_session, membre, nature="achat", fournisseur=f, jour=dt.date(2026, 10, 1), montant_centimes=m, description=f)
        for f, m in (("Castorama", 4500), ("Ikea", 12000))
    ]
    pieces = _lire(db_session, t, ecole, "expense_notes")
    assert {p["id"] for p in pieces} == {a.id for a in achats} and pieces[0]["expenses"][0]["receipt"] is False

    texte, carte = _proposer(db_session, t, ecole, "review_expense_notes", {
        "validate_ids": [achats[0].id], "refuse": [{"note_id": achats[1].id, "reason": "Facture illisible"}],
    })
    assert carte is not None and "Valider" in carte["lignes"][0] and "Facture illisible" in carte["lignes"][0]
    assert _faire(db_session, t, ecole, carte)[0]["ok"]
    assert _lire(db_session, t, ecole, "expense_notes") == []
    assert [p["id"] for p in _lire(db_session, t, ecole, "expense_notes", {"filter": "a_rembourser"})] == [achats[0].id]

    texte, carte = _proposer(db_session, t, ecole, "mark_expense_notes_paid", {"note_ids": [achats[0].id]})
    assert carte is not None and _faire(db_session, t, ecole, carte)[0]["ok"]
    texte, carte = _proposer(db_session, t, ecole, "review_expense_notes", {"validate_ids": [achats[0].id]})
    assert carte is None and "introuvables" in texte


def test_detail_d_une_ligne_desactiver_supprimer_et_niveau(db_session, ecole):
    t = ecole["tresorier"]
    ligne = _lire(db_session, t, ecole, "finance_operations", {"text": "pizza"})["lines"][0]
    detail = _lire(db_session, t, ecole, "finance_operation", {"operation_id": ligne["id"]})
    assert detail["label"].startswith("VIR PIZZA") and "entries" in detail
    plan = _lire(db_session, t, ecole, "finance_chart")
    assert plan["level"] == "simple" and plan["natures"]

    texte, carte = _proposer(db_session, t, ecole, "edit_chart_account", {"number": "6137", "label": "Salle", "nature": "depense"})
    _faire(db_session, t, ecole, carte)
    texte, carte = _proposer(db_session, t, ecole, "edit_chart_account", {"number": "6137", "label": "Salle", "active": False})
    assert "désactivé" in carte["lignes"][0] and _faire(db_session, t, ecole, carte)[0]["ok"]
    texte, carte = _proposer(db_session, t, ecole, "delete_chart_account", {"number": "6137"})
    assert "Supprimer" in carte["lignes"][0] and _faire(db_session, t, ecole, carte)[0]["ok"]
    assert all(a["number"] != "6137" for a in _lire(db_session, t, ecole, "finance_chart")["accounts"])

    texte, carte = _proposer(db_session, t, ecole, "set_accounting_level", {"level": "complet"})
    assert carte is not None and _faire(db_session, t, ecole, carte)[0]["ok"]
    balance = _lire(db_session, t, ecole, "finance_ag_document", {"document": "balance"})
    assert balance["accounts"]
    texte, carte = _proposer(db_session, t, ecole, "set_accounting_level", {"level": "complet"})
    assert carte is None and "déjà" in texte
    guide, carte = _proposer(db_session, t, ecole, "app_guide", {"module": "Financier"})
    assert carte is None and "⋯ › Plan comptable" in guide


def test_guide_du_financier_seulement_pour_qui_y_a_acces(db_session, ecole):
    """Le guide de l'appli (assistant/guide.py) : un module dont la personne
    n'a pas le droit, ou éteint dans l'école, n'apparaît pas."""
    assert "Financier" in _proposer(db_session, ecole["tresorier"], ecole, "app_guide", {})[0]
    texte, carte = _proposer(db_session, ecole["admin"], ecole, "app_guide", {"module": "finances"})
    assert carte is None and texte.startswith("Refusé") and "Financier" not in texte.split(":", 1)[1]
