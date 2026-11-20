"""Le reste du Financier ouvert à l'assistant (finances_contretemps/preparer.py,
Seb 20/11 : « tout le Financier ») : Balance sur une période, Compte de
résultat, Bilan actif-passif, Bilan › Préparer, caisse, comptes proposés ;
écritures par carte Faire / Annuler, réservées aux trésoriers."""

# ruff: noqa: F811 (fixture `ecole` importée)
import io
import json

import pytest
from test_finances_actions import _faire, _proposer, ecole  # noqa: F401
from test_finances_assemblies import make_pptx

from app import main
from documents_contretemps.adapter import membre_appelant

pytestmark = pytest.mark.rbac_reel


def _lire(db, compte, ecole, nom, args=None):
    texte, carte = _proposer(db, compte, ecole, nom, args or {})
    assert carte is None, texte
    return json.loads(texte)


def _complet(db, ecole):
    main.core.finances_accounting.set_level(db, ecole["membre"], "complet")


def _saison_passee(db, ecole):
    return main.core.finances_ag_documents.balance_season(db, ecole["id"])


def test_reserve_aux_tresoriers(db_session, ecole):
    for nom, args in (("finance_balance", {"view": "balance"}), ("finance_preparation", {"part": "etapes"}), ("finance_cash", {}),
                      ("set_season_budget", {"take_realised": True}), ("add_cash_line", {"date": "2026-10-01", "label": "x", "amount": 5})):
        texte, carte = _proposer(db_session, ecole["admin"], ecole, nom, args)
        assert carte is None and "trésoriers" in texte, nom


def test_balance_grand_livre_et_compte_de_resultat_sur_une_periode(db_session, ecole):
    t = ecole["tresorier"]
    saison = _saison_passee(db_session, ecole)
    resultat = _lire(db_session, t, ecole, "finance_balance", {"view": "compte_de_resultat", "season": saison.name})
    assert resultat["seasonName"] == saison.name and {"charges", "produits", "result", "previous"} <= resultat.keys()
    balance = _lire(db_session, t, ecole, "finance_balance", {"view": "balance", "season": saison.name})
    assert balance["accounts"] and all("balance" in a for a in balance["accounts"])
    courte = _lire(db_session, t, ecole, "finance_balance", {"view": "grand_livre", "season": saison.name,
                                                            "date_from": "2025-12-01", "date_to": "2025-12-31"})
    assert courte["start"] == "2025-12-01" and all("2025-12-01" <= l["date"] <= "2025-12-31" for l in courte["lines"])
    texte, carte = _proposer(db_session, t, ecole, "finance_balance", {"view": "bilan"})
    assert carte is None and "view" in texte


def test_bilan_actif_passif_en_engagement(db_session, ecole):
    t = ecole["tresorier"]
    saison = _saison_passee(db_session, ecole)
    texte, carte = _proposer(db_session, t, ecole, "finance_ag_document", {"document": "bilan", "season": saison.name})
    assert carte is None and "Engagement" in texte
    _complet(db_session, ecole)
    bilan = _lire(db_session, t, ecole, "finance_ag_document", {"document": "bilan", "season": saison.name})
    assert bilan["actif"]["tresorerie"] and round(bilan["totalActif"], 2) == round(bilan["totalPassif"], 2)


def test_etapes_releves_soldes_documents(db_session, ecole):
    t = ecole["tresorier"]
    saison = _saison_passee(db_session, ecole).name
    etapes = _lire(db_session, t, ecole, "finance_preparation", {"season": saison, "part": "etapes"})
    assert etapes["3_classify"]["withoutAccount"] > 0 and etapes["5_controls"]
    releves = _lire(db_session, t, ecole, "finance_preparation", {"season": saison, "part": "releves"})
    assert releves["accounts"] and all(m for a in releves["accounts"] for m in a["months"].values())
    soldes = _lire(db_session, t, ecole, "finance_preparation", {"season": saison, "part": "soldes_depart"})
    assert soldes["source"] == "releves" and soldes["bankCheck"]
    docs = _lire(db_session, t, ecole, "finance_preparation", {"season": saison, "part": "documents"})
    assert {r["kind"] for r in docs["rows"]} >= {"synthese"} and docs["budget"]["kind"] == "budget"
    texte, carte = _proposer(db_session, t, ecole, "finance_preparation", {"season": saison, "part": "fin_annee"})
    assert carte is None and "Engagement" in texte
    texte, carte = _proposer(db_session, t, ecole, "finance_preparation", {"season": saison, "part": "rien"})
    assert carte is None and "part" in texte


def test_budget_previsionnel(db_session, ecole):
    t = ecole["tresorier"]
    saison = _saison_passee(db_session, ecole).name
    texte, carte = _proposer(db_session, t, ecole, "set_season_budget", {"season": saison, "lines": {"99999": 10}})
    assert carte is None and "absent" in texte
    texte, carte = _proposer(db_session, t, ecole, "set_season_budget", {"season": saison, "take_realised": True})
    assert carte is not None and "Reprendre le réalisé".lower() in carte["lignes"][0].lower()
    assert _faire(db_session, t, ecole, carte)[0]["ok"]
    budget = _lire(db_session, t, ecole, "finance_preparation", {"season": saison, "part": "budget"})
    assert budget["filled"]
    ligne = (budget["charges"]["lines"] or budget["produits"]["lines"])[0]
    texte, carte = _proposer(db_session, t, ecole, "set_season_budget", {"season": saison, "lines": {ligne["number"]: 1234.5}})
    assert "1 234,50 €" in carte["lignes"][0] and _faire(db_session, t, ecole, carte)[0]["ok"]
    budget = _lire(db_session, t, ecole, "finance_preparation", {"season": saison, "part": "budget"})
    assert any(l["planned"] == 1234.5 for side in ("charges", "produits") for l in budget[side]["lines"])


def test_caisse(db_session, ecole):
    t = ecole["tresorier"]
    recette = next(a for a in main.core.finances_accounting.accounts(db_session, ecole["id"], active_only=True) if a.nature == "recette")
    texte, carte = _proposer(db_session, t, ecole, "add_cash_line",
                             {"date": "2026-10-03", "label": "Buvette gala", "amount": 85, "plan_account": recette.number})
    assert carte is not None and "85,00 €" in carte["lignes"][0] and recette.number in carte["lignes"][0]
    assert _faire(db_session, t, ecole, carte)[0]["ok"]
    caisse = _lire(db_session, t, ecole, "finance_cash")
    assert caisse["balance"] == 85 and caisse["lines"][0]["label"] == "Buvette gala"


def test_comptes_proposes(db_session, ecole):
    t = ecole["tresorier"]
    assert _lire(db_session, t, ecole, "finance_chart_proposals") == {"proposals": []}
    texte, carte = _proposer(db_session, t, ecole, "create_proposed_accounts", {})
    assert carte is None and "aucun compte proposé" in texte


def test_correction_du_rapport(db_session, ecole, monkeypatch):
    t = ecole["tresorier"]
    texte, carte = _proposer(db_session, t, ecole, "produce_financial_report", {})
    _faire(db_session, t, ecole, carte)
    bilan = main.finances_reports.list(db_session, ecole["membre"], ecole["saison"].id)[0]
    texte, carte = _proposer(db_session, t, ecole, "correct_financial_statement", {"report_id": bilan["id"], "instruction": "Plus court"})
    assert carte is None and "rédiger d'abord" in texte
    appels = []
    monkeypatch.setattr(main.core.finances_written, "get", lambda db, report_id: {"id": 1})
    monkeypatch.setattr(main.core.finances_written, "correct", lambda db, member, report_id, season, instruction: appels.append(instruction))
    texte, carte = _proposer(db_session, t, ecole, "correct_financial_statement", {"report_id": bilan["id"], "instruction": "Plus court"})
    assert carte is not None and "Plus court" in carte["lignes"][0]
    assert _faire(db_session, t, ecole, carte)[0]["ok"] and appels == ["Plus court"]


def test_ecriture_a_la_main_soldes_de_depart_et_fin_d_annee(db_session, ecole):
    t = ecole["tresorier"]
    saison = _saison_passee(db_session, ecole)
    comptes = main.core.finances_accounting.accounts(db_session, ecole["id"], active_only=True)
    debit = next(a for a in comptes if a.nature == "depense")
    credit = next(a for a in comptes if a.nature == "recette")
    # En Trésorerie, le service refuse au clic, comme à l'écran.
    texte, carte = _proposer(db_session, t, ecole, "add_manual_entry", {
        "season": saison.name, "date": saison.end_date, "label": "x", "debit_account": debit.number, "credit_account": credit.number, "amount": 40,
    })
    fait = _faire(db_session, t, ecole, carte)[0]
    assert not fait["ok"] and "Engagement" in fait["erreur"]
    _complet(db_session, ecole)
    texte, carte = _proposer(db_session, t, ecole, "add_manual_entry", {
        "season": saison.name, "date": "1999-01-01", "label": "x", "debit_account": debit.number, "credit_account": credit.number, "amount": 40,
    })
    assert carte is None and "dans la saison" in texte
    texte, carte = _proposer(db_session, t, ecole, "add_manual_entry", {
        "season": saison.name, "date": saison.end_date, "label": "Cotisation due", "debit_account": debit.number,
        "credit_account": credit.number, "amount": 40,
    })
    assert carte is not None and "40,00 €" in carte["lignes"][0] and _faire(db_session, t, ecole, carte)[0]["ok"]
    ecritures = _lire(db_session, t, ecole, "finance_preparation", {"season": saison.name, "part": "ecritures_main"})
    assert [e["label"] for e in ecritures["entries"]] == ["Cotisation due"]

    soldes = _lire(db_session, t, ecole, "finance_preparation", {"season": saison.name, "part": "soldes_depart"})
    banque = next(a for a in soldes["accounts"] if a["nature"] == "banque")
    texte, carte = _proposer(db_session, t, ecole, "set_opening_balances", {"season": saison.name, "balances": [{"number": "4019", "balance": -120}]})
    assert carte is None and "libellé" in texte
    texte, carte = _proposer(db_session, t, ecole, "set_opening_balances", {
        "season": saison.name, "balances": [{"number": "401", "label": "Fournisseurs", "balance": -120}],
    })
    assert carte is not None and "110" in carte["lignes"][0] and banque["number"] in carte["lignes"][0]
    assert _faire(db_session, t, ecole, carte)[0]["ok"]
    soldes = _lire(db_session, t, ecole, "finance_preparation", {"season": saison.name, "part": "soldes_depart"})
    assert soldes["source"] == "saisie" and any(a["number"] == "401" and a["balance"] == -120 for a in soldes["accounts"])
    texte, carte = _proposer(db_session, t, ecole, "set_opening_balances", {"season": saison.name, "from_previous_balance": True})
    assert carte is None and "Balance" in texte  # aucune Balance de l'an dernier dans Docs

    fin = _lire(db_session, t, ecole, "finance_preparation", {"season": saison.name, "part": "fin_annee"})
    texte, carte = _proposer(db_session, t, ecole, "validate_year_end_entries", {"season": saison.name, "choices": [{"key": "zzz"}]})
    assert carte is None and ("inconnue" in texte or "aucune" in texte)
    if fin["items"]:
        texte, carte = _proposer(db_session, t, ecole, "validate_year_end_entries", {"season": saison.name})
        assert carte is not None and _faire(db_session, t, ecole, carte)[0]["ok"]
        assert _lire(db_session, t, ecole, "finance_preparation", {"season": saison.name, "part": "fin_annee"})["validated"]


def test_documents_de_la_saison(db_session, ecole):
    t = ecole["tresorier"]
    saison = _saison_passee(db_session, ecole).name
    texte, carte = _proposer(db_session, t, ecole, "set_season_documents", {"season": saison, "choices": [{"document": "synthese", "choice": "same"}]})
    assert carte is None and "pas de fichier l'an dernier" in texte
    texte, carte = _proposer(db_session, t, ecole, "set_season_documents", {"season": saison, "choices": [
        {"document": "fec", "choice": "new"}, {"document": "synthese", "choice": "none"},
    ]})
    assert carte is not None and "FEC : Nouveau" in carte["lignes"][0] and "Compte de résultat : Non" in carte["lignes"][0]
    assert _faire(db_session, t, ecole, carte)[0]["ok"]
    docs = _lire(db_session, t, ecole, "finance_preparation", {"season": saison, "part": "documents"})
    choix = {r["kind"]: r["choice"] for r in docs["rows"]}
    assert choix["fec"] == "new" and choix["synthese"] == "none"


def test_ag_avec_un_powerpoint_de_docs(db_session, ecole, monkeypatch):
    t, saison = ecole["tresorier"], ecole["saison"]
    monkeypatch.setattr(main.documents_client.storage, "root", ecole["tmp"] / "docs")
    texte, carte = _proposer(db_session, t, ecole, "produce_financial_report", {})
    _faire(db_session, t, ecole, carte)
    qui = membre_appelant(db_session, t)
    dossier = main.documents_client.create_folder(db_session, qui, "private", None, "AG")
    pptx = make_pptx(ecole["tmp"] / "ag2324.pptx").read_bytes()
    fichier = main.documents_client.upload(db_session, qui, "private", dossier["id"], "AG 2023-2024.pptx", io.BytesIO(pptx))
    texte_pdf = main.documents_client.upload(db_session, qui, "private", dossier["id"], "notes.pdf", io.BytesIO(b"%PDF-1.4"))

    texte, carte = _proposer(db_session, t, ecole, "produce_general_assembly", {"docs_file_id": texte_pdf["id"]})
    assert carte is None and ".pptx" in texte
    texte, carte = _proposer(db_session, t, ecole, "produce_general_assembly", {"docs_file_id": 999999})
    assert carte is None and "Refusé" in texte
    texte, carte = _proposer(db_session, t, ecole, "produce_general_assembly", {"docs_file_id": fichier["id"], "title": "AG 2026"})
    assert carte is not None and "AG 2023-2024.pptx" in carte["lignes"][0]
    assert _faire(db_session, t, ecole, carte)[0]["ok"]
    ag = main.finances_assemblies.list(db_session, ecole["membre"], saison.id)[0]
    detail = main.finances_assemblies.get(db_session, ecole["membre"], ag["id"])
    assert "AG 2023-2024.pptx" in json.dumps(detail, ensure_ascii=False)
