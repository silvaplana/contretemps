"""Module finances, sous-module Comptes (spec/modules/financier.md) :
lecture d'un relevé PDF, import (doublons, archives), virements internes,
trous entre relevés, étanchéité entre écoles, droits (`rbac_reel`).
Les relevés sont fabriqués ici (même mise en page que ceux du Crédit
Mutuel, données inventées) : les vrais relevés ne vont jamais dans Git."""

import io
import tarfile
import zipfile

import py7zr
import pymupdf
import pytest
from conftest import entetes_session

from comptes import Comptes, roles
from ecoles import Ecoles
from finances import Finances, Member, StatementParseError, parse_statement
from finances.categories import categorize

COURANT = "C/C Connect Asso N° 00020461601 en euros (GD)"
LIVRET = "€ LIVRET BLEU ASSOCIATION N° 00020461602 en euros (GE)"

TRESORIER = Member(person_id=1, org_id=1, name="Julia Dho", is_treasurer=True)
AUTRE_ECOLE = Member(person_id=2, org_id=2, name="Ana Roux", is_treasurer=True)


def fr(amount_cents):
    """1234567 -> '12.345,67' (format des relevés)."""
    euros, cents = divmod(amount_cents, 100)
    return f"{euros:,}".replace(",", ".") + f",{cents:02d}"


def make_statement(account_line, start, operations, end_date=None, error=0):
    """PDF de relevé : start = (jj/mm/aaaa, solde en centimes), operations =
    [(date, libellé, montant en centimes, [lignes de détail])]."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    # Code technique de la banque dans la marge gauche (à ignorer).
    page.insert_text((6, 300), "X", fontsize=8)
    page.insert_text((82, 340), account_line, fontsize=8)
    for x, word in [(63, "Date"), (98, "Date"), (118, "valeur"), (161, "Opération"), (409, "Débit"), (431, "EUROS"), (480, "Crédit"), (506, "EUROS")]:
        page.insert_text((x, 367), word, fontsize=8)

    def right(x_right, y, text):
        page.insert_text((x_right - pymupdf.get_text_length(text, fontsize=8), y), text, fontsize=8)

    y = 386
    page.insert_text((158, y), f"SOLDE CREDITEUR AU {start[0]}", fontsize=8)
    right(534, y, fr(start[1]))
    balance = start[1]
    for date, label, amount, details in operations:
        y += 11
        page.insert_text((52, y), date, fontsize=8)
        page.insert_text((100, y), date, fontsize=8)
        page.insert_text((148, y), label, fontsize=8)
        right(460 if amount < 0 else 534, y, fr(abs(amount)))
        for line in details:
            y += 11
            page.insert_text((148, y), line, fontsize=8)
        balance += amount
    y += 15
    page.insert_text((304, y), "Total des mouvements", fontsize=8)
    y += 15
    page.insert_text((53, y), "Réf : 001", fontsize=8)
    page.insert_text((158, y), f"SOLDE CREDITEUR AU {end_date or operations[-1][0]}", fontsize=8)
    right(534, y, fr(balance + error))
    return doc.tobytes()


def test_parse_statement():
    pdf = make_statement(
        COURANT,
        ("01/06/2026", 429643),
        [
            ("02/06/2026", "PRLV SEPA GIMS", -15240, ["FACTURE FA26019948"]),
            ("24/06/2026", "VIR STRIPE TECHNOLOGY", 329074, []),
        ],
        end_date="30/06/2026",
    )
    statement = parse_statement(pdf)
    assert statement.account_number == "00020461601"
    assert (statement.start_date, statement.start_balance) == ("2026-06-01", 429643)
    assert (statement.end_date, statement.end_balance) == ("2026-06-30", 743477)
    first, second = statement.operations
    assert (first.date, first.label, first.details, first.amount) == ("2026-06-02", "PRLV SEPA GIMS", "FACTURE FA26019948", -15240)
    assert (second.label, second.amount) == ("VIR STRIPE TECHNOLOGY", 329074)


def test_parse_rejects_statement_that_does_not_add_up():
    pdf = make_statement(COURANT, ("01/06/2026", 1000), [("02/06/2026", "CB", -500, [])], error=1)
    with pytest.raises(StatementParseError, match="ne tombe pas juste"):
        parse_statement(pdf)


def test_parse_rejects_other_pdf():
    doc = pymupdf.open()
    doc.new_page().insert_text((50, 50), "Facture")
    with pytest.raises(StatementParseError):
        parse_statement(doc.tobytes())


def history():
    """Compte courant (2 relevés) + livret, avec un virement livret → courant."""
    return [
        ("c1.pdf", make_statement(COURANT, ("30/06/2024", 100000), [("03/07/2024", "CB DECATHLON", -20000, []), ("07/07/2024", "VIR DE ALLIANCE SAMBO", 50000, [])], "31/07/2024")),
        ("c2.pdf", make_statement(COURANT, ("31/07/2024", 130000), [("12/08/2024", "VIR SALAIRE", -37739, [])], "31/08/2024")),
        ("l1.pdf", make_statement(LIVRET, ("31/12/2023", 400000), [("07/07/2024", "VIR C/C EUROCOMPTE", -50000, [])], "31/07/2024")),
    ]


@pytest.fixture
def finances():
    return Finances()


def test_import_and_ledger(finances, db_session):
    report = finances.import_files(db_session, TRESORIER, history())
    assert len(report["imported"]) == 3 and not report["errors"]

    ledger = finances.get_ledger(db_session, TRESORIER)
    courant, livret = ledger["accounts"]
    assert (courant["name"], courant["balance"], courant["asOf"]) == ("Compte courant", 922.61, "2024-08-31")
    assert (livret["name"], livret["balance"]) == ("Livret Bleu", 3500.0)
    assert ledger["total"] == 4422.61
    assert ledger["issues"] == []
    assert courant["coverage"] == [{"from": "2024-06-30", "to": "2024-08-31", "statements": 2}]
    # Virement interne : une seule ligne, total inchangé.
    assert [r["label"] for r in ledger["rows"]] == ["VIR SALAIRE", "VIR C/C EUROCOMPTE", "CB DECATHLON"]
    transfer = ledger["rows"][1]
    assert transfer["transfer"] == {"from": "Livret Bleu", "to": "Compte courant"}
    assert transfer["amount"] == 500.0
    assert transfer["total"] == ledger["rows"][2]["total"] == 4800.0

    # Un compte seul : le virement est une opération ordinaire.
    alone = finances.get_ledger(db_session, TRESORIER, courant["id"])
    assert [r["amount"] for r in alone["rows"]] == [-377.39, 500.0, -200.0]
    assert alone["total"] == 922.61


def test_import_twice_and_zip(finances, db_session):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in history():
            archive.writestr(f"comptes/{name}", data)
    assert len(finances.import_files(db_session, TRESORIER, [("comptes.zip", buffer.getvalue())])["imported"]) == 3
    report = finances.import_files(db_session, TRESORIER, history())
    assert len(report["skipped"]) == 3 and not report["imported"]
    assert len(finances.get_ledger(db_session, TRESORIER)["rows"]) == 3  # virement interne : 1 ligne


def test_missing_statement_is_reported(finances, db_session):
    first, _, livret = history()
    later = ("c3.pdf", make_statement(COURANT, ("30/09/2024", 50000), [("05/10/2024", "CB", -1000, [])], "31/10/2024"))
    finances.import_files(db_session, TRESORIER, [first, livret, later])
    ledger = finances.get_ledger(db_session, TRESORIER)
    assert len(ledger["issues"]) == 1 and "il manque un relevé" in ledger["issues"][0]
    assert len(ledger["accounts"][0]["coverage"]) == 2


def test_import_7z_and_tar(finances, db_session, tmp_path):
    first, second, livret = history()
    seven = tmp_path / "a.7z"
    with py7zr.SevenZipFile(seven, "w") as archive:
        archive.writestr(first[1], first[0])
    tar = io.BytesIO()
    with tarfile.open(fileobj=tar, mode="w:gz") as archive:
        for name, data in (second, livret):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    report = finances.import_files(db_session, TRESORIER, [("a.7z", seven.read_bytes()), ("b.tar.gz", tar.getvalue())])
    assert sorted(i["file"] for i in report["imported"]) == ["c1.pdf", "c2.pdf", "l1.pdf"]


def test_each_organisation_sees_only_its_accounts(finances, db_session):
    """Même numéro de compte dans deux écoles : deux comptes distincts, et un
    virement ne se relie jamais avec l'autre école."""
    finances.import_files(db_session, TRESORIER, history())
    finances.import_files(db_session, AUTRE_ECOLE, history()[:1])
    autre = finances.get_ledger(db_session, AUTRE_ECOLE)
    assert [a["name"] for a in autre["allAccounts"]] == ["Compte courant"]
    assert autre["total"] == 1300.0 and not any(r["transfer"] for r in autre["rows"])
    assert finances.get_ledger(db_session, TRESORIER)["total"] == 4422.61
    with pytest.raises(LookupError):
        finances.get_ledger(db_session, AUTRE_ECOLE, finances.get_ledger(db_session, TRESORIER)["accounts"][1]["id"])


def test_only_treasurers_keep_accounts(finances, db_session):
    membre = Member(person_id=3, org_id=1, name="Margot")
    with pytest.raises(PermissionError):
        finances.get_ledger(db_session, membre)
    with pytest.raises(PermissionError):
        finances.import_files(db_session, membre, history())


@pytest.mark.parametrize(
    "label, details, category",
    [
        ("VIR STRIPE TECHNOLOGY", "", "Cotisations en ligne"),
        ("VIR HELLOASSOPAY R4WOXYY6WK2XP0Q HELLOASSO 35", "", "Cotisations en ligne"),
        ("VIR SEPA SALAIRE CHRISTOPHE CH3V26216L038172", "", "Salaires"),
        ("PRLV SEPA URSSAF PACA UR 937000002004519013", "", "URSSAF"),
        ("FACT SGT25089720011273", "DONT TVA 0,38EUR", "Frais bancaires"),
        ("PAIEMENT CB 2603 VOIRON", "FACTURE DIGITALEA", "Autres"),
        ("Intérêts Livret Bleu", "", "Intérêts"),
        ("CB DECATHLON", "", "Matériel"),
        ("VIR SIE LA CIOTAT", "SIE LA CIOTAT\nREMB. DGFIP - REMB VIRT", "Aides et remboursements"),
    ],
)
def test_categorize(label, details, category):
    assert categorize(label, details) == category


def test_ledger_rows_have_a_category(finances, db_session):
    finances.import_files(db_session, TRESORIER, history())
    ledger = finances.get_ledger(db_session, TRESORIER)
    assert {r["label"]: r["category"] for r in ledger["rows"]} == {
        "VIR SALAIRE": "Salaires",
        "VIR C/C EUROCOMPTE": "Virement interne",
        "CB DECATHLON": "Matériel",
    }
    assert ledger["categories"][-2:] == ["Autres", "Virement interne"]
    # Un compte seul : le virement interne reste classé à part.
    alone = finances.get_ledger(db_session, TRESORIER, ledger["accounts"][0]["id"])
    assert [r["category"] for r in alone["rows"]] == ["Salaires", "Virement interne", "Matériel"]


# --- Routes, avec les vraies sessions (trésorier, Super User, autres) ---


@pytest.fixture()
def ecole(db_session):
    comptes = Comptes()
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    tresorier = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia", email="julia@test.fr")
    comptes.ajouter_role(db_session, tresorier, roles.TRESORIER)
    admin = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Roux", prenom="Ana", email="ana@test.fr")
    return {"ecole": ecole, "tresorier": tresorier, "admin": admin}


@pytest.mark.rbac_reel
def test_routes(client, ecole):
    tresorier = entetes_session(ecole["tresorier"])
    files = [("files", (name, data, "application/pdf")) for name, data in history()]
    reponse = client.post("/finances/import", files=files, headers=tresorier)
    assert reponse.status_code == 200, reponse.text
    assert len(reponse.json()["imported"]) == 3
    assert client.get("/finances/ledger", headers=tresorier).json()["total"] == 4422.61
    assert client.get("/finances/ledger?account=99", headers=tresorier).status_code == 404
    saisons = client.get("/finances/seasons", headers=tresorier).json()
    assert len(saisons["seasons"]) == 1 and saisons["seasons"][0]["current"]
    # Un admin qui n'est pas trésorier n'a pas les comptes.
    admin = entetes_session(ecole["admin"])
    assert client.get("/finances/ledger", headers=admin).status_code == 403
    assert client.post("/finances/import", files=files, headers=admin).status_code == 403


@pytest.mark.rbac_reel
def test_super_user_keeps_the_accounts_of_the_chosen_school(client, db_session, ecole):
    su = Comptes().enregistrer_superuser(db_session, nom="Richard", prenom="Sébastien", email="su@test.fr", mot_de_passe_hache=None)
    sans_ecole = entetes_session(su)
    assert client.get("/finances/ledger", headers=sans_ecole).status_code == 403
    entetes = {**sans_ecole, "X-Ecole-Id": str(ecole["ecole"].id)}
    files = [("files", (name, data, "application/pdf")) for name, data in history()[:1]]
    assert client.post("/finances/import", files=files, headers=entetes).status_code == 200
    assert client.get("/finances/ledger", headers=entetes_session(ecole["tresorier"])).json()["total"] == 1300.0
