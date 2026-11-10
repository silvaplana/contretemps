"""Niveau Complet (financier.md §8.7) : écritures de tiers lettrées depuis
les pièces, soldes de départ saisis ou reportés de la clôture, clôture qui
verrouille la saison, écritures d'une opération."""

import pymupdf
import pytest
from test_finances import TRESORIER, make_statement, COURANT
from test_finances_ag_documents import SEASON, statements

from finances import Accounting, AgDocuments, AgPorts, Finances, Member, Season
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
    pieces[rows["CB AMAZON"]["id"]] = {"id": 1, "title": "Facture Amazon", "kind": "Achat", "nature": "achat", "date": "2025-09-01", "person": "", "amount": 39.9, "number": "AC-2025-001"}
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


def test_internal_transfers_go_through_580_at_full_level(full, db_session):
    finances, _, documents, _, _ = full
    transfer = next(r for r in finances.get_ledger(db_session, TRESORIER)["rows"] if r["transfer"])
    books = documents.books(db_session, TRESORIER, SEASON)
    # 512 (compte courant) → 580 → 512 (livret) : deux écritures, 580 soldé.
    lines = [(l.debit, l.credit) for l in books["580"].lines]
    assert books["580"].label == "Virements internes" and lines == [(10000, 0), (0, 10000)]
    assert books["580"].balance == 0
    assert any(l.credit == 10000 and l.label == transfer["label"] for l in books["5121"].lines)
    assert any(l.debit == 10000 and l.label == transfer["label"] for l in books["5122"].lines)
    # En Simple (trésorerie), le virement reste direct 512 → 512.
    assert "580" not in documents.books(db_session, TRESORIER, SEASON, full=False)


def test_the_treasurer_can_number_a_bank_account_like_the_previous_software(full, db_session):
    finances, _, documents, _, _ = full
    account = finances.get_ledger(db_session, TRESORIER)["allAccounts"][0]
    assert account["ledgerNumber"] == "5121"
    finances.rename_account(db_session, TRESORIER, account["id"], None, ledger_number="5123")
    books = documents.books(db_session, TRESORIER, SEASON)
    assert "5121" not in books and books["5123"].label == account["name"]
    assert any(l.journal == "BQ3" for l in books["5123"].lines)  # journal = BQ + dernier chiffre
    # Le nom ne bouge pas, la vérification des soldes de départ suit le numéro.
    assert finances.get_ledger(db_session, TRESORIER)["allAccounts"][0]["name"] == account["name"]
    numbers = [c["number"] for c in documents.opening(db_session, TRESORIER, SEASON)["bankCheck"]]
    assert "5123" in numbers and "5121" not in numbers


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
    # Le cadenas (§8.7) : les lignes de la saison sont validées à l'écran, dans
    # le Grand livre (colonne Type) et dans le FEC (ValidDate = la clôture) ;
    # un relevé de la saison n'entre plus.
    finances, *_ = full
    ledger = finances.get_ledger(db_session, TRESORIER)
    assert [(c["start"], c["end"]) for c in ledger["closings"]] == [("2025-09-01", "2026-08-31")]
    assert accounting.operation(db_session, TRESORIER, rows["PRLV MYSTERE"]["id"])["closed"] is True
    assert accounting.operation(db_session, TRESORIER, rows["CB BRICO"]["id"])["closed"] is False
    text = "".join(p.get_text() for p in pymupdf.open(stream=documents.grand_livre_pdf(db_session, TRESORIER, SEASON, "Contretemps"), filetype="pdf"))
    assert "Écritures validées par la clôture du" in text and "Type" in text
    closed_on = documents.closing(db_session, TRESORIER.org_id, SEASON.id).closed_at.strftime("%Y%m%d")
    fec_lines = documents.fec(db_session, TRESORIER, SEASON).decode("iso8859_15").splitlines()[1:]
    assert fec_lines and all(line.split("\t")[15] == closed_on for line in fec_lines)
    refused = finances.import_files(
        db_session, TRESORIER,
        [("c3.pdf", make_statement(COURANT, ("30/09/2025", 100000), [("05/10/2025", "CB TARDIVE", -1000, [])], "31/10/2025"))],
    )
    assert refused["imported"] == [] and "clôturée" in refused["errors"][0]["detail"]
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
    assert [h["closedAt"][:10] for h in documents.closing_history(db_session, TRESORIER.org_id, SEASON)] == [closed_on[:4] + "-" + closed_on[4:6] + "-" + closed_on[6:]]
    assert finances.get_ledger(db_session, TRESORIER)["closings"] == []
    assert accounting.operation(db_session, TRESORIER, rows["PRLV MYSTERE"]["id"])["closed"] is False
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


def test_unpaid_invoices_of_the_season_are_due_to_third_parties_at_full_level(full, db_session):
    """financier.md §8.10 étape 4 (Seb, 9/11) : au niveau Complet, une facture
    validée pas encore payée, datée de la saison, entre en charge le jour de la
    facture contre son tiers (401 / 467x), sans lettre ; hors saison ou au
    niveau Simple, rien."""
    finances, accounting, documents, rows, accounts = full
    documents.ports.unpaid = lambda db, org: [
        {"title": "Pesenti novembre", "amount": 678.0, "date": "2025-11-30", "nature": "honoraires", "account": "622", "person": "Pesenti"},
        {"title": "Castorama", "amount": 45.5, "date": "2026-03-10", "nature": "achat", "account": None},
        {"title": "Trop tard", "amount": 10.0, "date": "2026-09-02", "nature": "achat", "account": "606"},
    ]
    books = documents.books(db_session, TRESORIER, SEASONS[0])
    books.pop("_cutoff")
    pesenti = next(a for a in books.values() if a.number == "4672")
    assert [(l.date, l.journal, l.credit, l.letter) for l in pesenti.lines] == [("2025-11-30", "HO", 67800, "")]
    assert next(a for a in books.values() if a.number == "622").balance == 67800
    fournisseurs = next(a for a in books.values() if a.number.startswith("401"))
    assert [(l.date, l.credit) for l in fournisseurs.lines if l.label == "Castorama"] == [("2026-03-10", 4550)]
    a_classer = next(a for a in books.values() if a.number == "65900")  # sans compte de charge : à classer
    assert [(l.date, l.debit) for l in a_classer.lines if l.label == "Castorama"] == [("2026-03-10", 4550)]
    assert not any(l.label == "Trop tard" for a in books.values() for l in a.lines)
    # Le total débit = total crédit tient toujours.
    assert sum(l.debit for a in books.values() for l in a.lines) == sum(l.credit for a in books.values() for l in a.lines)
    # Niveau Simple : comptabilité de trésorerie, rien.
    simple = documents.books(db_session, TRESORIER, SEASONS[0], full=False)
    assert not any(l.label == "Castorama" for a in simple.values() if hasattr(a, "lines") for l in a.lines)


def test_manual_entries_go_through_the_od_journal_at_full_level(full, db_session):
    """financier.md §8.10 étape 4 : une écriture saisie à la main (cotisation
    due 411 contre 756, régularisation du 471) entre au journal OD au niveau
    Complet ; refusée hors saison, sur la banque, à zéro ou au niveau Simple."""
    finances, accounting, documents, rows, accounts = full
    accounts = {a["number"]: a for a in accounting.chart(db_session, TRESORIER)["accounts"]}
    entries = documents.add_manual_entry(
        db_session, TRESORIER, SEASONS[0],
        {"date": "2026-08-31", "label": "Cotisations dues au 31 août", "debitAccountId": accounts["411"]["id"], "creditAccountId": accounts["756"]["id"], "amount": "120"},
    )
    assert [(e["label"], e["debit"]["number"], e["credit"]["number"], e["amount"]) for e in entries] == [("Cotisations dues au 31 août", "411", "756", 120.0)]
    books = documents.books(db_session, TRESORIER, SEASONS[0])
    books.pop("_cutoff")
    assert [(l.journal, l.debit) for l in next(a for a in books.values() if a.number == "411").lines] == [("OD", 12000)]
    assert any(l.journal == "OD" and l.credit == 12000 for l in next(a for a in books.values() if a.number == "756").lines)
    assert sum(l.debit for a in books.values() for l in a.lines) == sum(l.credit for a in books.values() for l in a.lines)
    # Préparer les montre dans Hors banque.
    assert documents.preparation(db_session, TRESORIER, SEASONS[0], None)["offBank"]["entries"][0]["label"] == "Cotisations dues au 31 août"
    # Refus : hors saison, banque, même compte, zéro.
    base = {"label": "x", "debitAccountId": accounts["411"]["id"], "creditAccountId": accounts["756"]["id"], "amount": 1}
    for mauvais in ({"date": "2026-09-01"}, {"date": "2026-01-01", "amount": 0}, {"date": "2026-01-01", "creditAccountId": accounts["411"]["id"]}):
        with pytest.raises(ValueError):
            documents.add_manual_entry(db_session, TRESORIER, SEASONS[0], {**base, **mauvais})
    banque = next((a for a in accounting.chart(db_session, TRESORIER)["accounts"] if a["nature"] == "banque"), None)
    if banque is not None:
        with pytest.raises(ValueError):
            documents.add_manual_entry(db_session, TRESORIER, SEASONS[0], {**base, "date": "2026-01-01", "debitAccountId": banque["id"]})
    # Supprimer.
    documents.delete_manual_entry(db_session, TRESORIER, entries[0]["id"])
    assert documents.manual_entries(db_session, TRESORIER, SEASONS[0]) == []
    with pytest.raises(LookupError):
        documents.delete_manual_entry(db_session, TRESORIER, 999)


def test_bilan_actif_passif_balances_with_the_season_result(full, db_session):
    """financier.md §8.6 : le Bilan met à l'actif les soldes débiteurs des
    comptes de bilan (créances, banque, caisse), au passif les soldes
    créditeurs (dettes) et les fonds associatifs (report à nouveau, résultat
    de la saison) ; les deux totaux sont égaux."""
    finances, accounting, documents, rows, accounts = full
    b = documents.bilan(db_session, TRESORIER, SEASONS[0])
    assert b["totalActif"] == b["totalPassif"] > 0
    assert b["passif"]["fonds"][-1]["label"].startswith("Résultat de la saison") and b["passif"]["fonds"][-1]["amount"] == b["result"]
    assert any(l["number"].startswith("5") for l in b["actif"]["tresorerie"])
    assert all(l["amount"] > 0 for g in b["actif"].values() for l in g) and all(l["amount"] > 0 for l in b["passif"]["dettes"])
    content, name, media = documents.produce(db_session, TRESORIER, SEASONS[0], "bilan")
    assert name == "Bilan actif-passif 2025-2026.pdf" and media == "application/pdf"
    text = "".join(p.get_text() for p in pymupdf.open(stream=content, filetype="pdf"))
    assert "Total actif" in text and "Total passif" in text and "Fonds associatifs" in text
    assert "Écart actif" not in text


def test_a_new_professor_gets_a_fee_account_of_their_own(full, db_session):
    """Seb, 10/11 : un prof sans compte 467x n'est pas rangé chez un autre
    prof ; à sa première facture l'appli crée « 467n Honoraires Nom », au
    prochain numéro libre, et le garde."""
    _, accounting, documents, rows, accounts = full
    pieces = accounting.pieces(db_session, TRESORIER.org_id)
    accounting.set_lines(db_session, TRESORIER, rows["PRLV MYSTERE"]["id"], [{"accountId": accounts["613"]["id"]}])
    pieces[rows["PRLV MYSTERE"]["id"]] = {"id": 3, "title": "Honoraires Boyer", "kind": "Honoraires", "nature": "honoraires", "date": "2025-10-05", "person": "Sophie Boyer"}
    books = documents.books(db_session, TRESORIER, SEASON)
    books.pop("_cutoff")
    assert books["4673"].label == "Honoraires Sophie Boyer" and books["4673"].lines[0].letter
    chart = {a["number"]: a for a in accounting.chart(db_session, TRESORIER)["accounts"]}
    assert chart["4673"]["nature"] == "tiers" and "4674" not in chart
    # Déjà là : rien de créé la fois suivante ; Galli garde son compte.
    documents.books(db_session, TRESORIER, SEASON)
    assert "4674" not in {a["number"] for a in accounting.chart(db_session, TRESORIER)["accounts"]}
    assert books["4671"].lines[0].label == "Honoraires Galli"


def test_a_payment_that_does_not_match_the_invoice_stays_open_on_the_third_party(full, db_session):
    """financier.md §8.7 (Seb, 10/11, lettrage à la main) : la facture entre au
    tiers à son montant, le paiement au montant de la banque ; différents, les
    deux lignes restent sans lettre (écart à régler), et la charge est au
    montant de la facture."""
    _, accounting, documents, rows, accounts = full
    pieces = accounting.pieces(db_session, TRESORIER.org_id)
    pieces[rows["CB AMAZON"]["id"]]["amount"] = 50.0  # facture de 50 €, payée 39,90
    books = documents.books(db_session, TRESORIER, SEASON)
    books.pop("_cutoff")
    assert [(l.journal, l.debit, l.credit, l.letter) for l in books["401"].lines] == [("AC", 0, 5000, ""), ("BQ1", 3990, 0, "")]
    # Colonne Pièce : le numéro donné à la validation, repris dans le FEC (PieceRef).
    assert {l.piece for l in books["401"].lines} == {"AC-2025-001"}
    fec = documents.fec(db_session, TRESORIER, SEASON).decode("iso8859_15")
    assert "\tAC-2025-001\t" in fec
    assert books["401"].balance == -1010 and books["606"].lines[0].debit == 5000
    assert sum(a.debit for a in books.values()) == sum(a.credit for a in books.values())
    assert not any("Lettrage" in p for p in documents.fec_check(db_session, TRESORIER, SEASON)["problems"])


def test_reset_season_wipes_the_treasurer_work_and_keeps_the_bank(full, db_session):
    """§8.7 « Repartir à zéro sur cette saison » (Seb, 10/11) : pour s'exercer
    sans la trésorière. Comptes confirmés, écritures à la main, soldes de
    départ et clôture de la saison partent, le port défait les pièces ; les
    transactions, le plan comptable et l'autre saison restent. Le nom de la
    saison retapé confirme, trésorier seulement."""
    finances, accounting, documents, rows, accounts = full
    accounts = {a["number"]: a for a in accounting.chart(db_session, TRESORIER)["accounts"]}
    documents.add_manual_entry(
        db_session, TRESORIER, SEASON,
        {"date": "2026-08-31", "label": "Cotisations dues", "debitAccountId": accounts["411"]["id"], "creditAccountId": accounts["756"]["id"], "amount": "120"},
    )
    documents.set_opening(db_session, TRESORIER, SEASON, [{"number": "5121", "label": "Courant", "balance": 950}, {"number": "5122", "label": "Livret", "balance": 500}])
    documents.close(db_session, TRESORIER, SEASON)
    # Une ligne de l'autre saison, qui doit rester.
    accounting.set_lines(db_session, TRESORIER, rows["CB BRICO"]["id"], [{"accountId": accounts["606"]["id"]}])
    appels = []
    documents.ports.reset_pieces = lambda db, member, start, end, operation_ids: appels.append((start, end, sorted(operation_ids))) or 3

    with pytest.raises(ValueError, match="nom de la saison"):
        documents.reset_season(db_session, TRESORIER, SEASON, "2025-26")
    with pytest.raises(PermissionError):
        documents.reset_season(db_session, Member(person_id=9, org_id=TRESORIER.org_id, name="Ana", is_treasurer=False), SEASON, SEASON.name)
    assert appels == [] and documents.closing_status(db_session, TRESORIER.org_id, SEASON) is not None

    # Le plan mémorisé avant les bêtises revient : le 4672 de Pesenti et le
    # libellé du 606 ; le compte ajouté ensuite part, celui qui a servi
    # ailleurs (sur CB BRICO, l'autre saison) reste inactif.
    chart = accounting.chart(db_session, TRESORIER)
    assert chart["snapshots"] == [] and chart["snapshotSuggestion"] == "Plan de départ"
    first = accounting.memorize_chart(db_session, TRESORIER)
    assert first["comment"] == "Plan de départ" and first["accounts"] == len(chart["accounts"])
    extra = accounting.create_account(db_session, TRESORIER, {"number": "6061", "label": "Eau", "nature": "depense"})
    accounting.set_lines(db_session, TRESORIER, rows["CB BRICO"]["id"], [{"accountId": extra["id"]}])
    accounting.create_account(db_session, TRESORIER, {"number": "6062", "label": "Gaz", "nature": "depense"})
    accounting.update_account(db_session, TRESORIER, accounts["606"]["id"], {"number": "606", "label": "Achats divers", "nature": "depense"})
    accounting.delete_account(db_session, TRESORIER, accounts["4672"]["id"])
    # Le journal : la suggestion dit ce qui a changé, le commentaire est libre.
    assert accounting.suggest_snapshot_comment(db_session, TRESORIER.org_id) == "2 comptes ajoutés (6061 Eau, 6062 Gaz), 1 libellé modifié (606), 1 compte activé ou désactivé (4672)"
    second = accounting.memorize_chart(db_session, TRESORIER, "  Après les  factures d'octobre ")
    assert second["comment"] == "Après les factures d'octobre"
    assert [s["id"] for s in accounting.chart(db_session, TRESORIER)["snapshots"]] == [second["id"], first["id"]]
    with pytest.raises(LookupError):
        accounting.restore_chart(db_session, TRESORIER, 999)
    done = documents.reset_season(db_session, TRESORIER, SEASON, " 2025-2026 ", first["id"])
    assert done["pieces"] == 3 and done["lines"] == 3 and done["chart"]["id"] == first["id"]
    chart = {a["number"]: a for a in accounting.chart(db_session, TRESORIER)["accounts"]}
    assert chart["606"]["label"] == accounts["606"]["label"] and chart["4672"]["active"] is True
    assert "6062" not in chart and chart["6061"]["active"] is False
    [(start, end, operation_ids)] = appels
    assert (start, end) == ("2025-09-01", "2026-08-31")
    assert rows["CB AMAZON"]["id"] in operation_ids and rows["CB BRICO"]["id"] not in operation_ids
    assert documents.closing_status(db_session, TRESORIER.org_id, SEASON) is None
    assert documents.manual_entries(db_session, TRESORIER, SEASON) == []
    assert documents.opening(db_session, TRESORIER, SEASON)["source"] == "releves"
    ledger = finances.get_ledger(db_session, TRESORIER)
    assert ledger["closings"] == [] and len(ledger["rows"]) == len(rows)
    assert accounting.operation(db_session, TRESORIER, rows["CB AMAZON"]["id"])["lines"] == []
    assert [l["number"] for l in accounting.operation(db_session, TRESORIER, rows["CB BRICO"]["id"])["lines"]] == ["6061"]


def test_an_invoice_paid_in_two_transactions_is_one_charge_and_one_letter(full, db_session):
    """Seb, 10 novembre (De Luca, 296 = 140 + 156) : l'acompte paie la facture,
    le « Reste dû » (`settles`) solde le tiers ; une charge, une facture au
    tiers, deux paiements, une seule lettre quand la somme tombe juste."""
    _, accounting, documents, rows, accounts = full
    pieces = accounting.pieces(db_session, TRESORIER.org_id)
    pieces[rows["CB AMAZON"]["id"]]["amount"] = 51.9
    pieces[rows["PRLV MYSTERE"]["id"]] = {
        "id": 3, "title": "Reste dû : Facture Amazon", "kind": "Achat", "nature": "achat", "date": "2025-09-01",
        "person": "", "amount": 12.0, "number": "AC-2025-001", "settles": 1,
    }
    accounting.set_lines(db_session, TRESORIER, rows["PRLV MYSTERE"]["id"], [{"accountId": accounts["606"]["id"]}])
    books = documents.books(db_session, TRESORIER, SEASON)
    books.pop("_cutoff")
    assert sum(a.debit for a in books.values()) == sum(a.credit for a in books.values())
    assert [(l.journal, l.date, l.debit, l.credit, l.letter) for l in books["401"].lines] == [
        ("AC", "2025-09-01", 0, 5190, "AAA"), ("BQ1", "2025-09-03", 3990, 0, "AAA"), ("BQ1", "2025-09-20", 1200, 0, "AAA"),
    ]
    assert [(l.journal, l.debit) for l in books["606"].lines] == [("AC", 5190)]
    # Le reste payé plus tard que la saison : la facture et l'acompte restent ouverts, sans lettre.
    del pieces[rows["PRLV MYSTERE"]["id"]]
    books = documents.books(db_session, TRESORIER, SEASON)
    assert [l.letter for l in books["401"].lines] == ["", ""]
