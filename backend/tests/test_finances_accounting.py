"""Comptabilité du module finances (spec/modules/financier.md §8) : plan
comptable par défaut, proposition d'un compte (mots-clés puis historique),
confirmation et ventilation, caisse, réglage Simple / Complet, pièce sur la
ligne, étanchéité entre organisations."""

import pytest
from test_finances import AUTRE_ECOLE, COURANT, TRESORIER, make_statement

from finances import Accounting, AccountingError, Finances, Member
from finances.chart import label_key, propose
from finances.models import FinChartAccount


def statements():
    return [
        (
            "c1.pdf",
            make_statement(
                COURANT,
                ("31/08/2025", 100000),
                [
                    ("03/09/2025", "CB 0309 AMAZON 0010 CB*9481", -3990, ["Tapis"]),
                    ("05/09/2025", "VIR FACT PESENTI", -185000, []),
                    ("18/09/2025", "VIR HELLOASSO", 259800, []),
                    ("20/09/2025", "PRLV MYSTERE", -1200, []),
                ],
                "30/09/2025",
            ),
        ),
        (
            "c2.pdf",
            make_statement(
                COURANT,
                ("30/09/2025", 369610),
                [("03/10/2025", "CB 0310 AMAZON 0011 CB*9481", -1500, [])],
                "31/10/2025",
            ),
        ),
    ]


@pytest.fixture
def accounting():
    return Accounting(pieces=lambda db, org_id: {2: {"id": 7, "title": "Pesenti", "kind": "Honoraires"}})


@pytest.fixture
def finances(accounting, db_session):
    finances = Finances(accounting=accounting)
    finances.import_files(db_session, TRESORIER, statements())
    return finances


def test_label_key_drops_what_changes():
    assert label_key("CARTE 26/09/26 DECATHLON 0010 CB*9481") == "CARTE DECATHLON CB"
    assert label_key("12345") == ""


def test_default_chart_and_keyword_proposal(accounting, finances, db_session):
    chart = accounting.chart(db_session, TRESORIER)
    assert chart["level"] == "simple"
    numbers = {a["number"] for a in chart["accounts"]}
    assert {"606", "627", "756", "401", "471"} <= numbers

    ledger = finances.get_ledger(db_session, TRESORIER)
    by_label = {row["label"]: row for row in ledger["rows"]}
    amazon = by_label["CB 0309 AMAZON 0010 CB*9481"]
    assert amazon["account"] is None
    assert amazon["proposal"]["number"] == "606"
    assert "Amazon" in amazon["proposal"]["reason"]
    # Une recette ne va jamais dans un compte de dépense.
    assert by_label["VIR HELLOASSO"]["proposal"]["number"] == "706"
    assert by_label["PRLV MYSTERE"]["proposal"] is None
    # La pièce vient du port (l'opération 2 = Pesenti).
    assert by_label["VIR FACT PESENTI"]["piece"]["title"] == "Pesenti"
    assert ledger["counts"] == {"withoutAccount": 5, "withoutPiece": 4}


def test_confirm_then_history_proposes_same_account(accounting, finances, db_session):
    ledger = finances.get_ledger(db_session, TRESORIER)
    first_amazon = next(r for r in ledger["rows"] if r["label"].startswith("CB 0309 AMAZON"))
    account_607 = accounting.create_account(
        db_session, TRESORIER, {"number": "607", "label": "Tissus", "nature": "depense", "keywords": []}
    )
    sheet = accounting.set_lines(db_session, TRESORIER, first_amazon["id"], [{"accountId": account_607["id"]}])
    assert [(line["number"], line["amount"]) for line in sheet["lines"]] == [("607", -39.9)]

    ledger = finances.get_ledger(db_session, TRESORIER)
    by_label = {row["label"]: row for row in ledger["rows"]}
    assert by_label["CB 0309 AMAZON 0010 CB*9481"]["account"]["number"] == "607"
    # L'autre ligne Amazon (numéros différents) suit l'historique, pas le mot-clé.
    other = by_label["CB 0310 AMAZON 0011 CB*9481"]["proposal"]
    assert other["number"] == "607" and "1 fois" in other["reason"]
    assert accounting.chart(db_session, TRESORIER)["accounts"][-1]["used"] == 0
    used = next(a for a in accounting.chart(db_session, TRESORIER)["accounts"] if a["number"] == "607")
    assert used["used"] == 1


def test_split_must_add_up(accounting, finances, db_session):
    ledger = finances.get_ledger(db_session, TRESORIER)
    helloasso = next(r for r in ledger["rows"] if r["label"] == "VIR HELLOASSO")
    accounts = {a["number"]: a["id"] for a in accounting.chart(db_session, TRESORIER)["accounts"]}
    with pytest.raises(AccountingError, match="montant de la banque"):
        accounting.set_lines(
            db_session, TRESORIER, helloasso["id"],
            [{"accountId": accounts["706"], "amount": 2000}, {"accountId": accounts["756"], "amount": 500}],
        )
    sheet = accounting.set_lines(
        db_session, TRESORIER, helloasso["id"],
        [{"accountId": accounts["706"], "amount": 2298}, {"accountId": accounts["756"], "amount": 300}],
    )
    assert sorted(line["amount"] for line in sheet["lines"]) == [300.0, 2298.0]
    row = next(r for r in finances.get_ledger(db_session, TRESORIER)["rows"] if r["label"] == "VIR HELLOASSO")
    assert row["account"]["split"] is True
    # Compte retiré : la ligne redevient à classer.
    assert accounting.set_lines(db_session, TRESORIER, helloasso["id"], [])["lines"] == []


def test_chart_edits_and_deletion(accounting, finances, db_session):
    accounts = {a["number"]: a for a in accounting.chart(db_session, TRESORIER)["accounts"]}
    with pytest.raises(AccountingError, match="existe déjà"):
        accounting.create_account(db_session, TRESORIER, {"number": "606", "label": "Doublon", "nature": "depense"})
    with pytest.raises(AccountingError, match="chiffres"):
        accounting.create_account(db_session, TRESORIER, {"number": "6a", "label": "X", "nature": "depense"})
    renamed = accounting.update_account(
        db_session, TRESORIER, accounts["613"]["id"], {"number": "613", "label": "Location Galli", "event": "gala", "keywords": ["GALLI"]}
    )
    assert (renamed["label"], renamed["event"], renamed["keywords"]) == ("Location Galli", "gala", ["GALLI"])
    # Jamais utilisé : supprimé ; utilisé : inactif.
    accounting.delete_account(db_session, TRESORIER, accounts["658"]["id"])
    ledger = finances.get_ledger(db_session, TRESORIER)
    mystery = next(r for r in ledger["rows"] if r["label"] == "PRLV MYSTERE")
    accounting.set_lines(db_session, TRESORIER, mystery["id"], [{"accountId": accounts["627"]["id"]}])
    accounting.delete_account(db_session, TRESORIER, accounts["627"]["id"])
    chart = {a["number"]: a for a in accounting.chart(db_session, TRESORIER)["accounts"]}
    assert "658" not in chart and chart["627"]["active"] is False


def test_level_simple_to_full_only(accounting, db_session):
    assert accounting.set_level(db_session, TRESORIER, "complet") == "complet"
    with pytest.raises(AccountingError):
        accounting.set_level(db_session, TRESORIER, "simple")
    assert accounting.level(db_session, AUTRE_ECOLE.org_id) == "simple"


def test_cash_lines_and_withdrawal(accounting, finances, db_session):
    accounts = {a["number"]: a["id"] for a in accounting.chart(db_session, TRESORIER)["accounts"]}
    cash = accounting.add_cash_line(
        db_session, TRESORIER, {"date": "2025-10-05", "label": "Entrées en espèces", "amount": 150, "accountId": accounts["707"]}
    )
    assert cash["balance"] == 150.0 and cash["lines"][0]["account"]["number"] == "707"
    ledger = finances.get_ledger(db_session, TRESORIER)
    amazon = next(r for r in ledger["rows"] if r["label"].startswith("CB 0310"))
    with pytest.raises(AccountingError, match="montant"):
        accounting.add_cash_line(
            db_session, TRESORIER, {"date": "2025-10-06", "label": "Retrait", "amount": 20, "transferOperationId": amazon["id"]}
        )
    cash = accounting.add_cash_line(
        db_session, TRESORIER, {"date": "2025-10-06", "label": "Retrait", "amount": 15, "transferOperationId": amazon["id"]}
    )
    assert cash["balance"] == 165.0 and cash["lines"][0]["account"] is None
    cash = accounting.delete_cash_line(db_session, TRESORIER, cash["lines"][0]["id"])
    assert cash["balance"] == 150.0


def test_organisations_are_sealed(accounting, finances, db_session):
    ledger = finances.get_ledger(db_session, TRESORIER)
    operation = ledger["rows"][0]
    accounts = accounting.chart(db_session, TRESORIER)["accounts"]
    with pytest.raises(LookupError):
        accounting.operation(db_session, AUTRE_ECOLE, operation["id"])
    with pytest.raises(LookupError):
        accounting.update_account(db_session, AUTRE_ECOLE, accounts[0]["id"], {"number": "999", "label": "X"})
    with pytest.raises(PermissionError):
        accounting.chart(db_session, Member(person_id=3, org_id=1, name="Membre"))


def test_propose_prefers_longest_keyword():
    a = FinChartAccount(id=1, org_id=1, number="627", label="Banque", nature="depense", keywords=["FACT SGT"])
    b = FinChartAccount(id=2, org_id=1, number="622", label="Honoraires", nature="depense", keywords=["FACT"])
    assert propose([a, b], "FACT SGT TENUE DE COMPTE", "", -500).account_id == 1
    assert propose([a, b], "VIR FACT PESENTI", "", -500).account_id == 2
    assert propose([a, b], "VIR FACT PESENTI", "", 500) is None


def test_routes(client, db_session, monkeypatch):
    """Les routes répondent avec le membre fourni par l'appli hôte."""
    from app.main import app
    from finances_contretemps.adapter import membre_appelant

    app.dependency_overrides[membre_appelant] = lambda: TRESORIER
    try:
        chart = client.get("/finances/chart").json()
        assert chart["level"] == "simple" and len(chart["accounts"]) > 10
        created = client.post("/finances/chart", json={"number": "6226", "label": "Honoraires profs", "nature": "depense"})
        assert created.status_code == 201
        assert client.put("/finances/chart/level", json={"level": "complet"}).json() == {"level": "complet"}
        assert client.get("/finances/cash").json()["balance"] == 0
        assert client.get("/finances/operations/999").status_code == 404
    finally:
        app.dependency_overrides.pop(membre_appelant, None)
