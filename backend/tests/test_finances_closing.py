"""Niveau Complet (financier.md §8.7) : écritures de tiers lettrées depuis
les pièces, soldes de départ saisis ou reportés de la clôture, clôture qui
verrouille la saison, écritures d'une opération."""

import pytest
from test_finances import TRESORIER, make_statement, COURANT
from test_finances_ag_documents import SEASON, statements

from finances import Accounting, AgDocuments, AgPorts, Finances, Season
from finances.accounting import AccountingError
from finances.ag_documents import _letter, _third_party

NEXT = Season(id=2, name="2026-2027", start_date="2026-09-01", end_date="2027-08-31")
SEASONS = [SEASON, NEXT]


@pytest.fixture
def full(db_session):
    pieces = {}
    accounting = Accounting(pieces=lambda db, org: pieces)
    finances = Finances(accounting=accounting)
    finances.import_files(db_session, TRESORIER, statements())
    finances.import_files(
        db_session, TRESORIER,
        [("c2.pdf", make_statement(COURANT, ("31/08/2026", 100000), [("05/09/2026", "CB BRICO", -1000, [])], "30/09/2026"))],
    )
    documents = AgDocuments(ledger=finances.get_ledger, accounting=accounting, seasons=lambda db, org: SEASONS, ports=AgPorts(org_name=lambda db, org: "Contretemps"))
    accounting.set_level(db_session, TRESORIER, "complet")
    accounts = {a["number"]: a for a in accounting.chart(db_session, TRESORIER)["accounts"]}
    accounting.create_account(db_session, TRESORIER, {"number": "4671", "label": "Galli (location)", "nature": "tiers"})
    accounting.create_account(db_session, TRESORIER, {"number": "4672", "label": "Pesenti", "nature": "tiers"})
    rows = {r["label"]: r for r in finances.get_ledger(db_session, TRESORIER)["rows"]}
    pieces[rows["CB AMAZON"]["id"]] = {"id": 1, "title": "Facture Amazon", "kind": "Achat", "nature": "achat", "date": "2025-09-01", "person": ""}
    pieces[rows["VIR GALLI"]["id"]] = {"id": 2, "title": "Honoraires Galli", "kind": "Honoraires", "nature": "honoraires", "date": "2025-08-20", "person": "Marco Galli"}
    accounting.set_lines(db_session, TRESORIER, rows["CB AMAZON"]["id"], [{"accountId": accounts["606"]["id"]}])
    accounting.set_lines(db_session, TRESORIER, rows["VIR GALLI"]["id"], [{"accountId": accounts["613"]["id"]}])
    accounting.set_lines(db_session, TRESORIER, rows["VIR HELLOASSO"]["id"], [{"accountId": accounts["706"]["id"]}])
    return finances, accounting, documents, rows, accounts


def test_third_party_account_and_letters():
    class A:
        def __init__(self, number, label):
            self.number, self.label = number, label

    accounts = [A("401", "Fournisseurs"), A("4671", "Galli (location)"), A("4672", "Pesenti")]
    assert _third_party(accounts, {"nature": "achat"}).number == "401"
    assert _third_party(accounts, {"nature": "honoraires", "person": "Marco Galli"}).number == "4671"
    assert _third_party(accounts, {"nature": "frais", "person": "Inconnu"}).number == "4671"  # le plus court
    assert _third_party(accounts, None) is None and _third_party([], {"nature": "achat"}) is None
    assert [_letter(n) for n in (1, 2, 26, 27)] == ["AAA", "AAB", "AAZ", "ABA"]


def test_full_books_go_through_third_parties_with_letters(full, db_session):
    _, _, documents, rows, _ = full
    books = documents.books(db_session, TRESORIER, SEASON)
    books.pop("_cutoff")
    assert sum(a.debit for a in books.values()) == sum(a.credit for a in books.values())
    # Achat : 606 contre 401 le jour de la facture, paiement 401 contre 5121, même lettre.
    assert [(l.journal, l.date, l.debit, l.credit, l.letter) for l in books["401"].lines] == [
        ("AC", "2025-09-01", 0, 3990, "AAA"), ("BQ1", "2025-09-03", 3990, 0, "AAA"),
    ]
    assert books["606"].lines[0].journal == "AC" and books["606"].lines[0].debit == 3990
    # Honoraires : le 467x de la personne ; facture d'avant la saison datée au 1er jour.
    assert [(l.journal, l.date) for l in books["4671"].lines] == [("HO", "2025-09-01"), ("BQ1", "2025-09-05")]
    assert books["4671"].balance == 0 and books["613"].balance == 160000
    # Une recette ne passe pas par un tiers.
    assert all(l.journal.startswith("BQ") for l in books["706"].lines)
    # FEC : lettrage équilibré, date de lettrage = le paiement.
    fec = documents.fec_entries(db_session, TRESORIER, SEASON)
    lettered = [l for e in fec for l in e["lines"] if l["account"] == "401"]
    assert {(l["letter"], l["letterDate"]) for l in lettered} == {("AAA", "2025-09-03")}
    assert not any("Lettrage" in p for p in documents.fec_check(db_session, TRESORIER, SEASON)["problems"])
    entries = documents.operation_entries(db_session, TRESORIER, rows["CB AMAZON"]["id"], "2025-09-03")
    assert [(e["journal"], e["account"][:3], e["debit"], e["credit"]) for e in entries] == [
        ("AC", "401", 0, 39.9), ("AC", "606", 39.9, 0), ("BQ1", "401", 39.9, 0), ("BQ1", "512", 0, 39.9),
    ]


def test_opening_balances_entered_then_closing_carries_them(full, db_session):
    _, accounting, documents, rows, accounts = full
    opening = documents.opening(db_session, TRESORIER, SEASON)
    assert opening["source"] == "releves" and opening["closed"] is False
    by_number = {a["number"]: a for a in opening["accounts"]}
    assert by_number["5121"]["balance"] == 950.0 and by_number["5122"]["balance"] == 500.0 and by_number["110"]["balance"] == -1450.0
    assert "4671" in by_number and "471" in by_number
    # Le trésorier reprend la Balance de l'an dernier : un fournisseur à payer en plus.
    saved = documents.set_opening(
        db_session, TRESORIER, SEASON,
        [{"number": "5121", "label": "Courant", "balance": 950}, {"number": "5122", "label": "Livret", "balance": 500}, {"number": "401", "label": "Fournisseurs", "balance": -200}],
    )
    assert saved["source"] == "saisie"
    assert {a["number"]: a["balance"] for a in saved["accounts"] if a["balance"]} == {"5121": 950.0, "5122": 500.0, "401": -200.0, "110": -1250.0}
    assert saved["bankCheck"] == [
        {"number": "5121", "label": "Compte courant", "statements": 950.0, "entered": 950.0},
        {"number": "5122", "label": "Livret Bleu", "statements": 500.0, "entered": 500.0},
    ]
    books = documents.books(db_session, TRESORIER, SEASON)
    books.pop("_cutoff")
    assert books["401"].lines[0].journal == "AN" and books["401"].lines[0].credit == 20000
    assert sum(a.debit for a in books.values()) == sum(a.credit for a in books.values())

    # Clôture : résultat dans 110, soldes reportés, saison verrouillée.
    status = documents.close(db_session, TRESORIER, SEASON)
    result = sum(a.balance for a in books.values() if a.nature in ("depense", "recette"))
    assert status["result"] == result / 100 and documents.closing_status(db_session, TRESORIER.org_id, SEASON) == status
    with pytest.raises(AccountingError, match="clôturée"):
        accounting.set_lines(db_session, TRESORIER, rows["PRLV MYSTERE"]["id"], [{"accountId": accounts["606"]["id"]}])
    with pytest.raises(AccountingError, match="clôturée"):
        accounting.add_cash_line(db_session, TRESORIER, {"date": "2025-10-01", "label": "Vente", "amount": 5})
    with pytest.raises(ValueError, match="déjà"):
        documents.close(db_session, TRESORIER, SEASON)
    with pytest.raises(ValueError, match="clôturée"):
        documents.set_opening(db_session, TRESORIER, SEASON, [])
    # La saison suivante part des soldes reportés : 110 porte le résultat.
    following = documents.opening(db_session, TRESORIER, NEXT)
    assert following["source"] == "cloture"
    carried = {a["number"]: a["balance"] for a in following["accounts"] if a["balance"]}
    assert carried["110"] == -1250.0 + result / 100 and carried["401"] == -200.0
    assert sum(carried.values()) == pytest.approx(0)
    next_books = documents.books(db_session, TRESORIER, NEXT)
    next_books.pop("_cutoff")
    assert "AN" in {l.journal for l in next_books["110"].lines} and next_books["5121"].lines[-1].label == "CB BRICO"
    # Rouvrir : plus de verrou, la saison suivante repart des relevés.
    assert documents.reopen(db_session, TRESORIER, SEASON) is None
    accounting.add_cash_line(db_session, TRESORIER, {"date": "2025-10-01", "label": "Vente", "amount": 5})
    assert documents.opening(db_session, TRESORIER, NEXT)["source"] == "releves"
    with pytest.raises(ValueError, match="pas clôturée"):
        documents.reopen(db_session, TRESORIER, SEASON)


def test_closing_needs_full_level(db_session):
    accounting = Accounting()
    finances = Finances(accounting=accounting)
    finances.import_files(db_session, TRESORIER, statements())
    documents = AgDocuments(ledger=finances.get_ledger, accounting=accounting, seasons=lambda db, org: SEASONS)
    with pytest.raises(ValueError, match="Complet"):
        documents.close(db_session, TRESORIER, SEASON)
