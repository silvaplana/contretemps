"""Actions du Financier ouvertes à l'assistant (finances_contretemps/actions.py,
spec/modules/financier.md §7) : produire un bilan, une AG, un prévisionnel ;
refus clairs (droits, saison, bilan manquant, modèle). Vrais droits
(`rbac_reel`), calculs simulés."""

import pytest
from test_finances import FakeAnalyst, statements_for_reports
from test_finances_assemblies import FakeWriter, make_pptx
from test_finances_forecasts import FakeCoder

from app import main
from comptes import Comptes, roles
from ecoles import Ecoles
from finances.ports import Member
from finances_contretemps import saisons_de_l_ecole

pytestmark = pytest.mark.rbac_reel

actions = main.assistant_client.actions


@pytest.fixture()
def ecole(db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(main.finances_reports, "analyst", FakeAnalyst())
    monkeypatch.setattr(main.finances_reports, "background", False)
    monkeypatch.setattr(main.finances_assemblies, "storage", tmp_path / "ag")
    monkeypatch.setattr(main.finances_assemblies, "writer", FakeWriter())
    monkeypatch.setattr(main.finances_assemblies, "background", False)
    monkeypatch.setattr(main.finances_forecasts, "coder", FakeCoder())
    monkeypatch.setattr(main.finances_forecasts, "background", False)
    comptes = Comptes()
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    tresorier = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia", email="julia@test.fr")
    comptes.ajouter_role(db_session, tresorier, roles.TRESORIER)
    admin = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Roux", prenom="Ana", email="ana@test.fr")
    membre = Member(person_id=1, org_id=ecole.id, name="Julia Dho", is_treasurer=True)
    main.finances_client.import_files(db_session, membre, statements_for_reports())
    saison = saisons_de_l_ecole(db_session, ecole.id)[-1]
    return {"id": ecole.id, "tresorier": tresorier, "admin": admin, "membre": membre, "saison": saison, "tmp": tmp_path}


def _proposer(db, compte, ecole, nom, args):
    return actions.propose(db, compte, ecole["id"], compte.id, nom, args)


def _faire(db, compte, ecole, carte):
    return actions.execute(db, ecole["id"], compte.id, carte["jeton"])


def test_outils_montres_a_tous_mais_reserves_aux_tresoriers(db_session, ecole):
    noms = {t["name"] for t in actions.tools(admin=False)}
    assert {"produce_financial_report", "produce_general_assembly", "produce_forecast"} <= noms
    texte, carte = _proposer(db_session, ecole["admin"], ecole, "produce_financial_report", {})
    assert carte is None and "trésoriers" in texte


def test_bilan_produit_puis_ag_a_partir_du_bilan(db_session, ecole):
    tresorier, membre, saison = ecole["tresorier"], ecole["membre"], ecole["saison"]
    # Sans bilan calculé, l'AG est refusée avec la marche à suivre.
    texte, carte = _proposer(db_session, tresorier, ecole, "produce_general_assembly", {})
    assert carte is None and "produce_financial_report" in texte

    texte, carte = _proposer(db_session, tresorier, ecole, "produce_financial_report", {"instructions": "Court", "model": "claude-haiku-5-5"})
    assert carte is not None and f"Bilan {saison.name}" in carte["lignes"][0] and "Haiku 5.5" in carte["lignes"][0]
    assert _faire(db_session, tresorier, ecole, carte)[0]["ok"]
    bilans = main.finances_reports.list(db_session, membre, saison.id)
    assert len(bilans) == 1 and bilans[0]["status"] == "idle" and bilans[0]["hasResult"]

    # Pas de PowerPoint modèle : refusé, sauf si le modèle général existe.
    texte, carte = _proposer(db_session, tresorier, ecole, "produce_general_assembly", {"season": saison.name})
    assert carte is None and "modèle" in texte
    main.finances_assemblies.set_template(membre, make_pptx(ecole["tmp"] / "modele.pptx").read_bytes())
    texte, carte = _proposer(db_session, tresorier, ecole, "produce_general_assembly", {"title": "AG de juin", "state": "valide"})
    assert carte is not None and "AG de juin" in carte["lignes"][0] and f"Bilan {saison.name}" in carte["lignes"][0]
    assert _faire(db_session, tresorier, ecole, carte)[0]["ok"]
    ags = main.finances_assemblies.list(db_session, membre, saison.id)
    assert len(ags) == 1 and ags[0]["name"] == "AG de juin" and ags[0]["state"] == "valide" and ags[0]["status"] == "idle"

    # Une AG à partir du PowerPoint d'une autre AG, désignée par son nom.
    texte, carte = _proposer(db_session, tresorier, ecole, "produce_general_assembly", {"template": "AG de juin"})
    assert carte is not None and "AG de juin : PowerPoint" in carte["lignes"][0]
    texte, carte = _proposer(db_session, tresorier, ecole, "produce_general_assembly", {"template": "AG de 1999"})
    assert carte is None and "introuvable" in texte


def test_previsionnel_produit_avec_date_de_depart(db_session, ecole):
    tresorier, membre, saison = ecole["tresorier"], ecole["membre"], ecole["saison"]
    texte, carte = _proposer(db_session, tresorier, ecole, "produce_forecast", {"start_date": "1999-01-01"})
    assert carte is None and "dans la saison" in texte
    texte, carte = _proposer(db_session, tresorier, ecole, "produce_forecast", {"start_date": saison.start_date, "instructions": "Salaire 1000 €"})
    assert carte is not None and f"Prévision {saison.name}" in carte["lignes"][0]
    assert _faire(db_session, tresorier, ecole, carte)[0]["ok"]
    previsions = main.finances_forecasts.list(db_session, membre, saison.id)
    assert len(previsions) == 1 and previsions[0]["status"] == "idle" and previsions[0]["endBalance"] is not None
    assert previsions[0]["startDate"] == saison.start_date


def test_refus_saison_etat_et_modele(db_session, ecole):
    tresorier = ecole["tresorier"]
    for args, mot in (({"season": "1999-2000"}, "introuvable"), ({"state": "final"}, "état"), ({"model": "gpt"}, "modèle")):
        texte, carte = _proposer(db_session, tresorier, ecole, "produce_financial_report", args)
        assert carte is None and mot in texte, texte
