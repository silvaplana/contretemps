"""Documents de l'AG (spec/modules/financier.md §8.6) : grand livre en
mémoire équilibré, Synthèse par classe avec trésorerie, événement et
fournisseurs à payer, Balance et Grand livre en PDF, honoraires par prof,
lignes sans compte « à classer », retrait au distributeur, bilan par compte."""

import pymupdf
import pytest
from openpyxl import load_workbook
from test_finances import COURANT, LIVRET, TRESORIER, make_statement

from finances import Accounting, AgDocuments, AgPorts, Finances, Season
from finances.report import compute_report

SEASON = Season(id=1, name="2025-2026", start_date="2025-09-01", end_date="2026-08-31")


def statements():
    return [
        (
            "c0.pdf",
            make_statement(COURANT, ("31/07/2025", 100000), [("10/08/2025", "CB AVANT SAISON", -5000, [])], "31/08/2025"),
        ),
        (
            "c1.pdf",
            make_statement(
                COURANT,
                ("31/08/2025", 95000),
                [
                    ("03/09/2025", "CB AMAZON", -3990, []),
                    ("05/09/2025", "VIR GALLI", -160000, []),
                    ("18/09/2025", "VIR HELLOASSO", 259800, []),
                    ("20/09/2025", "PRLV MYSTERE", -1200, []),
                    ("22/09/2025", "RETRAIT DAB", -20000, []),
                    ("25/09/2025", "VIR LIVRET", -10000, []),
                ],
                "30/09/2025",
            ),
        ),
        ("l1.pdf", make_statement(LIVRET, ("31/08/2025", 50000), [("26/09/2025", "VIR C/C", 10000, [])], "30/09/2025")),
    ]


@pytest.fixture
def world(db_session):
    accounting = Accounting()
    finances = Finances(accounting=accounting)
    finances.import_files(db_session, TRESORIER, statements())
    ports = AgPorts(
        unpaid=lambda db, org: [{"title": "Pesenti", "amount": 678.0}],
        fees=lambda db, org, start, end: [
            {"person": "Pesenti", "month": "2025-10", "amount": 1850.0},
            {"person": "Pesenti", "month": "2025-11", "amount": 1850.0},
            {"person": "Revelles", "month": "2025-10", "amount": 678.0},
        ],
        org_name=lambda db, org: "Contretemps",
    )
    documents = AgDocuments(ledger=finances.get_ledger, accounting=accounting, seasons=lambda db, org: [SEASON], ports=ports)
    accounts = {a["number"]: a for a in accounting.chart(db_session, TRESORIER)["accounts"]}
    accounting.update_account(db_session, TRESORIER, accounts["613"]["id"], {"number": "613", "label": "Location Galli", "event": "gala"})
    accounting.update_account(db_session, TRESORIER, accounts["707"]["id"], {"number": "707", "label": "Entrées", "event": "gala"})
    rows = {r["label"]: r for r in finances.get_ledger(db_session, TRESORIER)["rows"]}
    accounting.set_lines(db_session, TRESORIER, rows["CB AMAZON"]["id"], [{"accountId": accounts["606"]["id"]}])
    accounting.set_lines(db_session, TRESORIER, rows["VIR GALLI"]["id"], [{"accountId": accounts["613"]["id"]}])
    accounting.set_lines(
        db_session, TRESORIER, rows["VIR HELLOASSO"]["id"],
        [{"accountId": accounts["706"]["id"], "amount": 2298}, {"accountId": accounts["756"]["id"], "amount": 300}],
    )
    accounting.add_cash_line(
        db_session, TRESORIER, {"date": "2025-09-22", "label": "Retrait", "amount": 200, "transferOperationId": rows["RETRAIT DAB"]["id"]}
    )
    accounting.add_cash_line(
        db_session, TRESORIER, {"date": "2025-09-28", "label": "Entrées du gala", "amount": 150, "accountId": accounts["707"]["id"]}
    )
    return finances, accounting, documents


def test_books_are_balanced_and_carry_the_opening_treasury(world, db_session):
    _, _, documents = world
    books = documents.books(db_session, TRESORIER, SEASON)
    books.pop("_cutoff")
    assert sum(a.debit for a in books.values()) == sum(a.credit for a in books.values())
    # Report à nouveau = trésorerie au 31/08 : 950,00 (courant) + 500,00 (livret).
    assert books["110"].balance == -145000
    assert books["5121"].lines[0].debit == 95000 and books["5122"].lines[0].debit == 50000
    # Le retrait va dans la caisse, pas dans « à classer » ; le mystère y va.
    assert books["530"].balance == 20000 + 15000
    assert books["65900"].balance == 1200
    # Virement interne : d'un 512 à l'autre, aucun compte de charge.
    assert books["5122"].balance == 60000 and "VIR LIVRET" in [l.label for l in books["5122"].lines]


def test_synthese_by_class_with_event_and_treasury(world, db_session):
    _, _, documents = world
    s = documents.synthese(db_session, TRESORIER, SEASON)
    charges = {line["number"]: line["amount"] for c in s["charges"] for line in c["lines"]}
    produits = {line["number"]: line["amount"] for p in s["produits"] for line in p["lines"]}
    assert charges == {"606": 39.9, "613": 1600.0, "65900": 12.0}
    assert produits == {"706": 2298.0, "756": 300.0, "707": 150.0}
    assert (s["totalCharges"], s["totalProduits"], s["result"]) == (1651.9, 2748.0, 1096.1)
    assert [c["code"] for c in s["charges"]] == ["60", "61", "65"]
    assert s["treasuryTotal"] == pytest.approx(1450 + 1096.1 + 678 * 0)  # trésorerie = départ + résultat
    assert s["unpaid"] == [{"title": "Pesenti", "amount": 678.0}] and s["unpaidTotal"] == 678.0
    assert s["events"] == [{"event": "gala", "resources": 150.0, "cost": 1600.0, "profit": -1450.0}]
    assert s["unclassified"] == 12.0


def test_documents_are_produced(world, db_session):
    _, accounting, documents = world
    content, name, media = documents.produce(db_session, TRESORIER, SEASON, "synthese")
    assert name == "Synthèse Dépenses-Recettes 2025-2026.xlsx" and "spreadsheet" in media
    sheet = load_workbook(filename=__import__("io").BytesIO(content)).active
    assert sheet["A1"].value == "Contretemps — Synthèse Dépenses-Recettes 2025-2026"
    for kind, text in (("balance", "Balance 2025-2026"), ("grand-livre", "Grand livre 2025-2026")):
        content, name, media = documents.produce(db_session, TRESORIER, SEASON, kind)
        assert media == "application/pdf" and name.endswith(".pdf")
        page_text = "".join(p.get_text() for p in pymupdf.open(stream=content, filetype="pdf"))
        assert text in page_text and "Report à nouveau" in page_text
        # Format comptable standard (§8.6) : en-tête, période, devise, totaux du modèle.
        assert "Édition du" in page_text and "Devise : EUR" in page_text and "Comptes 110 à" in page_text
        expected = ("Total pour le compte", "Total du Grand-Livre") if kind == "grand-livre" else ("Total des comptes de Bilan", "Total des comptes de Résultat", "Total de la Balance")
        assert all(t in page_text for t in expected)
    content, name, _ = documents.produce(db_session, TRESORIER, SEASON, "honoraires")
    sheet = load_workbook(filename=__import__("io").BytesIO(content)).active
    assert [c.value for c in sheet[2]] == ["Professeur", "2025-10", "2025-11", "Total"]
    assert [c.value for c in sheet[3]] == ["Pesenti", 1850.0, 1850.0, 3700.0]
    with pytest.raises(ValueError):
        documents.produce(db_session, TRESORIER, SEASON, "autre")
    assert [d["id"] for d in documents.kinds("simple")] == ["synthese", "fec"]
    assert len(documents.kinds("complet")) == 6


def test_balance_on_screen_shows_its_period_and_can_be_narrowed(world, db_session):
    """Comptes › ⋯ › Balance : la période est dite, la Balance s'équilibre, et
    une période plus courte ne garde que ses écritures."""
    _, _, documents = world
    b = documents.balance(db_session, TRESORIER, SEASON)
    assert (b["seasonName"], b["start"], b["end"], b["knownUntil"], b["closed"]) == ("2025-2026", "2025-09-01", "2026-08-31", "2025-09-30", False)
    by_number = {a["number"]: a for a in b["accounts"]}
    assert round(sum(a["debit"] for a in b["accounts"]), 2) == round(sum(a["credit"] for a in b["accounts"]), 2)
    assert by_number["606"]["debit"] == 39.9 and by_number["606"]["lines"][0]["label"] == "CB AMAZON"
    narrow = documents.balance(db_session, TRESORIER, SEASON, start="2025-09-10", end="2025-09-21")
    assert narrow["start"] == "2025-09-10" and narrow["end"] == "2025-09-21"
    assert "606" not in {a["number"] for a in narrow["accounts"]} and "706" in {a["number"] for a in narrow["accounts"]}
    # Hors saison : bornée à la saison.
    assert documents.balance(db_session, TRESORIER, SEASON, start="2020-01-01")["start"] == "2025-09-01"
    assert documents.balance_season(db_session, TRESORIER.org_id).id == SEASON.id


def test_report_adds_up_by_confirmed_account(world, db_session):
    finances, _, _ = world
    report = compute_report(finances.get_ledger(db_session, TRESORIER), SEASON.start_date, SEASON.end_date)
    expense = {r["category"]: r["amount"] for r in report["expense"]}
    assert expense["Location Galli"] == 1600.0 and expense["Fournitures et petit équipement"] == 39.9
    # Sans compte : catégorie par mots-clés comme avant, à classer par l'IA.
    assert "Autres" in expense
    unclassified = [op for op in report["operations"] if op["bankCategory"] == "Autres"]
    assert {op["label"] for op in unclassified} == {"PRLV MYSTERE", "RETRAIT DAB"}


def test_in_docs_returns_the_stored_file_id(world, db_session):
    _, _, documents = world
    stored = []
    documents.ports.store = lambda db, member, path, files: stored.append((path, [n for n, _ in files])) or [42]
    assert documents.in_docs(db_session, TRESORIER, SEASON, "balance") == 42
    assert stored == [(["AG"], ["Balance 2025-2026.pdf"])]
    with pytest.raises(ValueError):
        documents.in_docs(db_session, TRESORIER, SEASON, "autre")


def test_fec_has_the_18_columns_and_balanced_entries(world, db_session):
    _, accounting, documents = world
    content, name, media = documents.produce(db_session, TRESORIER, SEASON, "fec")
    assert name == "FEC 2025-2026.txt" and media.startswith("text/plain")
    rows = [r.split("\t") for r in content.decode("iso8859_15").removesuffix("\r\n").split("\r\n")]
    assert rows[0][:5] == ["JournalCode", "JournalLib", "EcritureNum", "EcritureDate", "CompteNum"] and len(rows[0]) == 18
    assert all(len(r) == 18 for r in rows)
    # À-nouveaux en premier, au premier jour ; montants à virgule.
    assert rows[1][0] == "AN" and rows[1][3] == "20250901" and rows[1][2] == "1"
    galli = [r for r in rows if r[10] == "VIR GALLI"]
    assert {(r[4], r[11], r[12]) for r in galli} == {("613", "1600,00", "0,00"), ("5121", "0,00", "1600,00")}
    assert len({r[2] for r in galli}) == 1  # une seule écriture
    for number in {r[2] for r in rows[1:]}:
        lines = [r for r in rows[1:] if r[2] == number]
        cents = lambda v: int(v.replace(",", ""))  # noqa: E731
        assert sum(cents(r[11]) - cents(r[12]) for r in lines) == 0, number

    # Contrôle : le prélèvement sans compte empêche le FEC d'être juste.
    check = documents.fec_check(db_session, TRESORIER, SEASON)
    assert not check["ok"] and check["problems"] == ["1 ligne(s) à classer (12,00 €) : Comptes › Sans compte."]
    assert any("Niveau Simple" in n for n in check["notes"])
    accounts = {a["number"]: a for a in accounting.chart(db_session, TRESORIER)["accounts"]}
    finances = world[0]
    mystere = next(r for r in finances.get_ledger(db_session, TRESORIER)["rows"] if r["label"] == "PRLV MYSTERE")
    accounting.set_lines(db_session, TRESORIER, mystere["id"], [{"accountId": accounts["627"]["id"]}])
    assert documents.fec_check(db_session, TRESORIER, SEASON)["ok"]


def test_preparation_counts_the_steps_and_confirms_accounts_in_bulk(world, db_session):
    """Bilan › Préparer (financier.md §8.10, Seb 9/11) : relevés, soldes de
    départ, un compte sur chaque transaction bancaire (à confirmer une par une
    ou « Valider le compte » par compte proposé), contrôles en clair."""
    finances, accounting, documents = world
    calendar = finances.statement_calendar(db_session, TRESORIER, SEASON.start_date, SEASON.end_date, today="2025-10-15")
    etat = documents.preparation(db_session, TRESORIER, SEASON, calendar)
    assert etat["season"]["name"] == "2025-2026" and etat["level"] == "simple"
    assert etat["statements"]["accounts"] == 2 and etat["statements"]["ok"] is True
    assert etat["opening"] == {"source": "releves", "mismatches": 0, "toCarry": False, "ok": True}  # niveau Simple : la trésorerie suffit
    classify = etat["classify"]
    # Amazon, Galli et HelloAsso sont classés ; les virements internes n'ont pas de compte.
    sans = [l["label"] for l in classify["unsure"]] + [o["label"] for g in classify["sure"] for o in g["operations"]]
    assert sorted(sans) == ["PRLV MYSTERE", "RETRAIT DAB"] and classify["withoutAccount"] == 2 and classify["ok"] is False
    assert [c["ok"] for c in etat["controls"]] == [True, True, False, False, True]
    assert "2 transaction(s) sans compte" in etat["controls"][2]["detail"]

    # « Valider le compte » : les deux d'un coup sur 627 ; un virement interne ou une ligne déjà classée est ignoré.
    accounts = {a["number"]: a for a in accounting.chart(db_session, TRESORIER)["accounts"]}
    rows = {r["label"]: r for r in finances.get_ledger(db_session, TRESORIER)["rows"]}
    ids = [rows["PRLV MYSTERE"]["id"], rows["RETRAIT DAB"]["id"], rows["CB AMAZON"]["id"], rows["VIR LIVRET"]["id"]]
    assert accounting.confirm_many(db_session, TRESORIER, ids, accounts["627"]["id"]) == 2
    etat = documents.preparation(db_session, TRESORIER, SEASON, calendar)
    assert etat["classify"] == {"withoutAccount": 0, "unsure": [], "sure": [], "ok": True}
    assert etat["controls"][2]["ok"] is True
    # Un membre n'y a pas droit.
    from finances import Member

    with pytest.raises(PermissionError):
        documents.preparation(db_session, Member(person_id=2, org_id=1, name="Margot", is_treasurer=False), SEASON, calendar)


def test_comparison_flags_big_gaps_until_the_treasurer_explains(world, db_session):
    """financier.md §8.10 étape 6 : compte par compte, la saison et la
    précédente ; un écart de plus de 30 % (ou un compte nouveau / disparu) est
    marqué « ? » tant qu'il n'est pas expliqué en une ligne."""
    finances, accounting, documents = world
    previous = Season(id=0, name="2024-2025", start_date="2024-09-01", end_date="2025-08-31")
    documents.seasons = lambda db, org: [previous, SEASON]
    # Sans rien en 2024-25 : chaque compte de 2025-26 est nouveau, donc à expliquer.
    comparison = documents.comparison(db_session, TRESORIER, SEASON)
    assert comparison["previousSeason"] == "2024-2025"
    flagged = {l["number"]: l for l in comparison["lines"] if l["flag"]}
    assert "613" in flagged and flagged["613"]["pct"] is None and flagged["613"]["current"] == 1600.0
    assert comparison["unexplained"] == len(flagged) > 0
    # Une explication lève le « ? » ; vide, elle l'efface.
    after = documents.set_note(db_session, TRESORIER, SEASON, "613", "  Gala déplacé à Galli, salle plus grande ")
    assert next(l for l in after["lines"] if l["number"] == "613")["note"] == "Gala déplacé à Galli, salle plus grande"
    assert after["unexplained"] == comparison["unexplained"] - 1
    assert documents.notes(db_session, TRESORIER.org_id, SEASON) == {"613": "Gala déplacé à Galli, salle plus grande"}
    assert documents.set_note(db_session, TRESORIER, SEASON, "613", "")["unexplained"] == comparison["unexplained"]
    # Préparer porte la comparaison et son contrôle ; hors banque : caisse et factures non payées.
    etat = documents.preparation(db_session, TRESORIER, SEASON, None)
    assert etat["comparison"]["unexplained"] == comparison["unexplained"]
    assert etat["controls"][-1]["ok"] is False and "marqué(s)" in etat["controls"][-1]["detail"]
    assert etat["offBank"]["unpaid"] == [{"title": "Pesenti", "amount": 678.0}] and etat["offBank"]["unpaidInBooks"] is False
    assert etat["offBank"]["cash"] == 350.0  # retrait 200 + entrées du gala 150
    # Première saison : pas de comparaison, rien à expliquer.
    documents.seasons = lambda db, org: [SEASON]
    assert documents.comparison(db_session, TRESORIER, SEASON) == {**documents.comparison(db_session, TRESORIER, SEASON), "previousSeason": None, "unexplained": 0}


def test_a_cheque_deposit_is_never_sure_and_is_split_like_the_previous_ones(world, db_session):
    """financier.md §8.10 étape 3 : une remise de chèques n'est jamais classée
    « sûre » (la banque ne dit pas ce que payent les chèques) ; la fiche
    propose de la ventiler comme les remises précédentes."""
    from finances.chart import is_cheque_deposit

    assert is_cheque_deposit("REM CHQ 0012345") and is_cheque_deposit("Remise de chèques N°12") and is_cheque_deposit("REMISE CHEQUE")
    assert not is_cheque_deposit("CB REMORQUES CHAMPAGNE") and not is_cheque_deposit("VIR HELLOASSO")
    finances, accounting, documents = world
    finances.import_files(
        db_session, TRESORIER,
        [("c2.pdf", make_statement(COURANT, ("30/09/2025", 159610), [("02/10/2025", "REM CHQ 0012345", 42000, []), ("09/10/2025", "REM CHQ 0012346", 15000, [])], "31/10/2025"))],
    )
    etat = documents.preparation(db_session, TRESORIER, SEASON, None)
    remises = [l for l in etat["classify"]["unsure"] if l["chequeDeposit"]]
    assert sorted(l["label"] for l in remises) == ["REM CHQ 0012345", "REM CHQ 0012346"]
    assert not any(o["label"].startswith("REM CHQ") for g in etat["classify"]["sure"] for o in g["operations"])
    # Première remise : pas d'habitude, le trésorier ventile à la main Cours / Cotisations.
    accounts = {a["number"]: a for a in accounting.chart(db_session, TRESORIER)["accounts"]}
    rows = {r["label"]: r for r in finances.get_ledger(db_session, TRESORIER)["rows"]}
    fiche = accounting.operation(db_session, TRESORIER, rows["REM CHQ 0012345"]["id"])
    assert fiche["chequeDeposit"] is True and fiche["splitSuggestion"] == []
    accounting.set_lines(
        db_session, TRESORIER, rows["REM CHQ 0012345"]["id"],
        [{"accountId": accounts["706"]["id"], "amount": 300}, {"accountId": accounts["756"]["id"], "amount": 120}],
    )
    # Deuxième remise : la fiche propose les mêmes comptes.
    fiche = accounting.operation(db_session, TRESORIER, rows["REM CHQ 0012346"]["id"])
    assert [a["number"] for a in fiche["splitSuggestion"]] == ["706", "756"]
    assert documents.preparation(db_session, TRESORIER, SEASON, None)["classify"]["withoutAccount"] == 3
