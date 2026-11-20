"""Écritures de fin d'année (spec/modules/financier.md §8.14, Seb 20/11) :
l'appli propose par règles fixes, la trésorière choisit et valide, le grand
livre recalcule les écritures, leur reprise et les dotations des saisons
suivantes."""

import datetime as dt

import pytest
from test_finances import COURANT, TRESORIER, make_statement

from finances import Accounting, AgDocuments, AgPorts, Finances, Season
from finances import year_end

BEFORE = Season(id=1, name="2024-2025", start_date="2024-09-01", end_date="2025-08-31")
SEASON = Season(id=2, name="2025-2026", start_date="2025-09-01", end_date="2026-08-31")
AFTER = Season(id=3, name="2026-2027", start_date="2026-09-01", end_date="2027-08-31")


@pytest.fixture
def world(db_session):
    accounting = Accounting()
    finances = Finances(accounting=accounting)
    rent = [(f"05/{m:02d}/{y}", "VIR SALLE DOJO", -18000, []) for y, m in [(2025, 9), (2025, 10), (2025, 11), (2025, 12)] + [(2026, m) for m in range(1, 8)]]
    operations = sorted(
        [
            ("02/06/2025", "PRLV OVH", -6000, []),
            ("05/07/2025", "PRLV MAIF", -42000, []),
            ("10/10/2025", "CB TATAMIS PRO", -240000, []),
            ("01/06/2026", "PRLV OVH", -6000, []),
            ("03/07/2026", "PRLV MAIF", -42000, []),
            ("20/07/2026", "VIR HELLOASSO", 124000, []),
        ] + rent,
        key=lambda o: (o[0][6:], o[0][3:5], o[0][:2]),
    )
    finances.import_files(db_session, TRESORIER, [("c.pdf", make_statement(COURANT, ("31/05/2025", 1000000), operations, "31/08/2026"))])
    accounting.set_level(db_session, TRESORIER, "complet")
    documents = AgDocuments(
        ledger=finances.get_ledger, accounting=accounting, seasons=lambda db, org: [BEFORE, SEASON, AFTER],
        ports=AgPorts(org_name=lambda db, org: "ASC"),
    )
    accounts = {a["number"]: a for a in accounting.chart(db_session, TRESORIER)["accounts"]}
    target = {"OVH": "623", "MAIF": "616", "TATAMIS": "606", "HELLOASSO": "756", "DOJO": "613"}
    for r in finances.get_ledger(db_session, TRESORIER)["rows"]:
        number = next(n for word, n in target.items() if word in r["label"])
        accounting.set_lines(db_session, TRESORIER, r["id"], [{"accountId": accounts[number]["id"]}])
    return accounting, documents


def balances(documents, db, season):
    books = documents.books(db, TRESORIER, season)
    books.pop("_cutoff")
    assert sum(a.balance for a in books.values()) == 0
    return {a.number: a.balance for a in books.values()}


def test_the_app_proposes_the_four_kinds_with_an_advised_choice(world, db_session):
    _, documents = world
    data = documents.year_end(db_session, TRESORIER, SEASON)
    items = {(i["kind"], i["text"].split(",")[0].split(" :")[0]): i for i in data["items"]}
    assert not data["validated"] and data["next"] == "2026-2027"
    maif = items[("prepaid_expense", "Maif")]
    assert maif["amount"] == 350.0 and maif["advised"] and maif["keep"]
    assert "10 mois sur 12 concernent 2026-2027" in maif["text"] and maif["reason"] == "Concerne sept. 2026 à juin 2027."
    assert maif["lines"] == [
        {"account": "486 Charges constatées d'avance", "debit": 350.0, "credit": 0},
        {"account": "616 Assurances", "debit": 0, "credit": 350.0},
    ]
    ovh = items[("prepaid_expense", "Ovh")]
    assert ovh["amount"] == 45.0 and not ovh["advised"] and not ovh["keep"] and ovh["reason"].startswith("Moins de 100 €")
    assert items[("prepaid_income", "Cotisations")]["amount"] == 1240.0
    rent = items[("invoice_due", "Salle Dojo")]
    assert rent["amount"] == 180.0 and "rien en août 2026" in rent["text"]
    mats = items[("depreciation", "Tatamis Pro")]
    assert mats["years"] == 5 and mats["byYears"]["5"]["amount"] == 440.0 and mats["byYears"]["5"]["effect"] == 1960.0
    assert mats["byYears"]["3"]["amount"] == round(2400 * 11 / 36, 2)
    # Rien n'est écrit tant que rien n'est validé.
    assert "486" not in balances(documents, db_session, SEASON)


def test_validated_choices_enter_the_books_and_cancel_removes_them(world, db_session):
    accounting, documents = world
    before = balances(documents, db_session, SEASON)
    data = documents.year_end(db_session, TRESORIER, SEASON)
    mats = next(i for i in data["items"] if i["kind"] == "depreciation")
    done = documents.set_year_end(db_session, TRESORIER, SEASON, [{"key": mats["key"], "keep": True, "years": 3}])
    assert done["validated"] and done["resultBefore"] == data["resultBefore"]
    after = balances(documents, db_session, SEASON)
    assert after["486"] == 35000 and after["616"] == before["616"] - 35000
    assert after["487"] == -124000 and after.get("756", 0) == 0
    assert after["408"] == -18000 and after["613"] == before["613"] + 18000
    assert after["2154"] == 240000 and after["28154"] == -73333 and after["6811"] == 73333 and after.get("606", 0) == 0
    assert after["623"] == before["623"]  # le petit montant est laissé
    numbers = {a.number for a in accounting.accounts(db_session, TRESORIER.org_id)}
    assert {"486", "487", "408", "2154", "28154", "6811"} <= numbers
    bilan = documents.bilan(db_session, TRESORIER, SEASON)
    assert [l["amount"] for l in bilan["actif"]["immobilisations"]] == [240000, -73333] and bilan["totalActif"] == bilan["totalPassif"]
    back = documents.cancel_year_end(db_session, TRESORIER, SEASON)
    assert not back["validated"] and balances(documents, db_session, SEASON) == before


def test_next_season_takes_back_the_advances_and_goes_on_depreciating(world, db_session):
    _, documents = world
    documents.set_year_end(db_session, TRESORIER, SEASON, [])
    documents.close(db_session, TRESORIER, SEASON)
    with pytest.raises(ValueError):
        documents.cancel_year_end(db_session, TRESORIER, SEASON)
    after = balances(documents, db_session, AFTER)
    assert after.get("486", 0) == 0 and after["616"] == 35000  # l'assurance payée d'avance devient la charge de la saison
    assert after.get("487", 0) == 0 and after["756"] == -124000
    assert after.get("408", 0) == 0 and after["613"] == -18000
    assert after["2154"] == 240000 and after["6811"] == 48000 and after["28154"] == -(44000 + 48000)


def test_depreciation_adds_up_to_the_price():
    bought = dt.date(2025, 10, 10)
    seasons = [(dt.date(2025 + i, 9, 1), dt.date(2026 + i, 8, 31)) for i in range(7)]
    assert sum(year_end.allowance(100000, bought, 3, s, e) for s, e in seasons) == 100000
    assert year_end.allowance(240000, bought, 5, *seasons[0]) == 44000
    assert year_end.allowance(240000, bought, 5, *seasons[5]) == 4000  # le dernier mois
    assert year_end.allowance(240000, bought, 5, *seasons[6]) == 0
