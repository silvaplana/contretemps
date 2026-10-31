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
        if amount is None:  # ligne d'information, sans montant
            continue
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


def test_parse_ignores_information_line_without_amount():
    """Livret du CIC : « 01/01/2023 01/01/2023 NOUVEAU TAUX DU LOBNL TRIPLEX »,
    deux dates sans montant. Ce n'est pas une opération : ignorée (le relevé
    était refusé, « Montant introuvable »). Le solde reste vérifié."""
    pdf = make_statement(
        LIVRET,
        ("31/12/2022", 500000),
        [("01/01/2023", "NOUVEAU TAUX DU LOBNL TRIPLEX", None, []), ("15/01/2023", "VERSEMENT", 10000, [])],
    )
    statement = parse_statement(pdf)
    assert [(op.label, op.amount) for op in statement.operations] == [("VERSEMENT", 10000)]


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
def test_routes(client, db_session, ecole):
    Comptes().create(db_session, ecole_id=ecole["ecole"].id, role="professeur", nom="Pesenti", prenom="Agnès", email="ap@test.fr")
    tresorier = entetes_session(ecole["tresorier"])
    files = [("files", (name, data, "application/pdf")) for name, data in history()]
    reponse = client.post("/finances/import", files=files, headers=tresorier)
    assert reponse.status_code == 200, reponse.text
    assert len(reponse.json()["imported"]) == 3
    assert client.get("/finances/ledger", headers=tresorier).json()["total"] == 4422.61
    assert client.get("/finances/ledger?account=99", headers=tresorier).status_code == 404
    # Le PDF de chaque relevé est rangé dans Docs › Saison du relevé ›
    # Financier › RELEVES BANCAIRES › <compte> ; la saison passée qui manquait
    # est créée (Seb, 30/10).
    details = [i["detail"] for i in reponse.json()["imported"]]
    assert {d.rsplit(" › ", 1)[1] for d in details} == {"COMPTE COURANT", "LIVRET BLEU"}, details
    assert all("Financier › RELEVES BANCAIRES ›" in d for d in details), details
    saisons = client.get("/finances/seasons", headers=tresorier).json()["seasons"]
    assert [(s["name"], s["current"]) for s in saisons] == [("2023-2024", False), ("2026-2027", True)]
    assert all("Docs › 2023-2024 ›" in d for d in details), details
    # Dossiers vides de la trésorière sous Financier de la saison en cours.
    from app import main
    from documents.models import DocNode
    from sqlalchemy import select

    def enfants(parent_id):
        return {n.name: n.id for n in db_session.scalars(select(DocNode).where(DocNode.parent_id == parent_id, DocNode.deleted_at.is_(None)))}

    financier = main.documents_client.reserved_folder(db_session, ecole["ecole"].id, "Financier", None)
    racines = enfants(financier.id)
    assert {"RELEVES BANCAIRES", "ACHATS", "HONORAIRES", "VENTES"} <= racines.keys()
    assert set(enfants(racines["VENTES"])) == {"COTISATIONS", "COURS", "PARTICIPATION GALA"}
    assert set(enfants(racines["RELEVES BANCAIRES"])) == {"COMPTE COURANT", "LIVRET BLEU"}
    assert set(enfants(racines["HONORAIRES"])) == {"AGNES PESENTI"}
    # Réimporter range les PDF déjà importés (relevés d'avant le rangement),
    # sans doublon dans Docs ni dans les lignes.
    again = client.post("/finances/import", files=files, headers=tresorier).json()
    assert again["imported"] == [] and all("rangé dans Docs" in i["detail"] for i in again["skipped"])
    courant = enfants(enfants(enfants(main.documents_client.reserved_folder(
        db_session, ecole["ecole"].id, "Financier", saisons[0]["id"]).id)["RELEVES BANCAIRES"])["COMPTE COURANT"])
    assert len(courant) == 2
    assert client.get("/finances/ledger", headers=tresorier).json()["total"] == 4422.61
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


# --- Bilan (sous-module, spec §4) : compte d'exploitation, analyse simulée ---

from finances import FinancialReports, ReportError  # noqa: E402
from finances.ai import Analysis, AnalysisError, cost_usd  # noqa: E402
from finances.ports import Season  # noqa: E402
from finances.report import compute_report  # noqa: E402

SEASONS = [
    Season(1, "2024-2025", "2024-07-01", "2025-06-30"),
    Season(2, "2025-2026", "2025-07-01", "2026-06-30"),
    Season(3, "2026-2027", "2026-07-01", "2027-06-30", current=True),
]


class FakeAnalyst:
    """IA simulée : classe les opérations « Autres » et renvoie une analyse."""

    def __init__(self, classify=None, error=None):
        self.classify = classify or {}
        self.error = error
        self.calls = []

    def analyze(self, model, data, prompt):
        self.calls.append((model, data, prompt))
        if self.error:
            raise AnalysisError(self.error, cost=0.01)
        ids = {op["libelle"]: op["operationId"] for op in data["operationsAClasser"]}
        return Analysis(
            classifications={ids[label]: category for label, category in self.classify.items() if label in ids},
            analysis=["Ligne 1", "Ligne 2"],
            model=model,
            served_by="claude-sonnet-5-5",
            cost=0.09,
        )


def statements_for_reports():
    """Compte courant et livret, de juin 2024 à août 2026 : une saison
    2024-2025 complète, une 2025-2026 complète, 2026-2027 en cours."""
    return [
        ("c1.pdf", make_statement(COURANT, ("01/06/2024", 100000), [("05/10/2024", "VIR STRIPE TECHNOLOGY", 500000, []), ("10/11/2024", "VIR SALAIRE NOVEMBRE", -100000, [])], "30/06/2025")),
        ("c2.pdf", make_statement(COURANT, ("30/06/2025", 500000), [
            ("31/07/2025", "VIR SALAIRE JUILLET", -120000, []),
            ("20/08/2025", "VIR SEPA FFST", 20000, []),
            ("15/09/2025", "VIR STRIPE TECHNOLOGY", 600000, []),
            ("20/09/2025", "VIR SEPA FFST", -50000, []),
            ("07/12/2025", "VIR PIZZA AG 29 NOV", -18680, []),
            ("24/06/2026", "CTR CLT 102780897200020300801", 329074, []),
        ], "31/08/2026")),
        ("l1.pdf", make_statement(LIVRET, ("01/06/2024", 300000), [("31/12/2025", "INTERETS", 6794, [])], "31/08/2026")),
    ]


@pytest.fixture
def costs():
    return []


@pytest.fixture
def ledger_db(db_session, finances):
    finances.import_files(db_session, TRESORIER, statements_for_reports())
    return db_session


def make_reports(finances, analyst, costs):
    return FinancialReports(
        ledger=finances.get_ledger,
        seasons=lambda db, org_id: SEASONS,
        note_cost=lambda db, org_id, cost, detail: costs.append((org_id, cost)),
        analyst=analyst,
        background=False,
    )


def test_compute_report_balances_and_categories(ledger_db, finances):
    report = compute_report(finances.get_ledger(ledger_db, TRESORIER), "2025-07-01", "2026-06-30")
    # Courant 1000 + 5000 − 1000, livret 3000.
    assert report["opening"] == 8000.0
    assert report["income"] == [
        {"category": "Cotisations en ligne", "amount": 6000.0},
        {"category": "Autres", "amount": 3103.94},  # 3290,74 − 186,80
        {"category": "Intérêts", "amount": 67.94},
    ]
    # Licences nettes : 500 payées − 200 remboursées.
    assert report["expense"] == [{"category": "Salaires", "amount": 1200.0}, {"category": "FFST (licences)", "amount": 300.0}]
    assert report["totalIncome"] == 9171.88 and report["totalExpense"] == 1500.0
    assert report["closing"] == 15671.88
    assert report["verification"] == {"expected": 15671.88, "actual": 15671.88, "gap": 0.0, "ok": True}
    assert report["months"][0] == {"month": "2025-07", "opening": 8000.0, "closing": 6800.0, "amounts": {"Salaires": -1200.0}}
    assert report["months"][-1]["closing"] == 15671.88


def test_current_season_stops_at_last_known_day(ledger_db, finances):
    report = compute_report(finances.get_ledger(ledger_db, TRESORIER), "2026-07-01", "2027-06-30")
    assert report["cutoff"] == "2026-08-31"
    assert report["income"] == [] and report["expense"] == []
    assert report["opening"] == report["closing"] == 15671.88
    assert report["verification"]["ok"]


def test_run_classifies_others_and_notes_cost(ledger_db, finances, costs):
    analyst = FakeAnalyst({"VIR PIZZA AG 29 NOV": "Réception AG", "CTR CLT 102780897200020300801": "Reprise autre association"})
    reports = make_reports(finances, analyst, costs)
    created = reports.create(ledger_db, TRESORIER, {"seasonId": 2, "name": "Bilan AG", "prompt": "", "model": "claude-sonnet-5-5"})
    assert created["status"] == "idle" and created["result"] is None

    done = reports.run(ledger_db, TRESORIER, created["id"], {"prompt": "Ton simple", "model": "claude-fable-5-1"})
    assert done["status"] == "idle"
    assert done["prompt"] == "Ton simple" and done["model"] == "claude-fable-5-1"
    model, data, prompt = analyst.calls[0]
    assert (model, prompt) == ("claude-fable-5-1", "Ton simple")
    assert [op["libelle"] for op in data["operationsAClasser"]] == ["VIR PIZZA AG 29 NOV", "CTR CLT 102780897200020300801"]
    assert data["saisonsPrecedentes"][0]["saison"] == "2024-2025"

    result = done["result"]
    assert {r["category"]: r["amount"] for r in result["income"]}["Reprise autre association"] == 3290.74
    assert {r["category"]: r["amount"] for r in result["expense"]}["Réception AG"] == 186.8
    assert "Autres" not in result["net"]
    assert result["verification"]["ok"]
    assert result["previous"]["season"] == "2024-2025"
    assert result["previous"]["net"]["Cotisations en ligne"] == 5000.0
    assert result["analysis"] == ["Ligne 1", "Ligne 2"]
    assert result["modelLabel"] == "Fable 5.1"

    reports.run(ledger_db, TRESORIER, created["id"], {})
    assert reports.get(ledger_db, TRESORIER, created["id"])["aiCostUsd"] == pytest.approx(0.18)
    assert costs == [(1, pytest.approx(0.09)), (1, pytest.approx(0.09))]


def test_run_error_is_reported_and_cost_kept(ledger_db, finances, costs):
    reports = make_reports(finances, FakeAnalyst(error="L'analyse de ce bilan a été refusée."), costs)
    created = reports.create(ledger_db, TRESORIER, {"seasonId": 2, "name": "Essai"})
    done = reports.run(ledger_db, TRESORIER, created["id"], {})
    assert done["status"] == "error" and done["error"] == "L'analyse de ce bilan a été refusée."
    assert done["result"] is None and done["aiCostUsd"] == pytest.approx(0.01)


def test_only_one_official_report_per_season_and_per_organisation(db_session, finances, costs):
    reports = make_reports(finances, FakeAnalyst(), costs)
    first = reports.create(db_session, TRESORIER, {"seasonId": 2, "name": "A", "state": "officiel"})
    second = reports.create(db_session, TRESORIER, {"seasonId": 2, "name": "B"})
    other = reports.create(db_session, TRESORIER, {"seasonId": 1, "name": "C", "state": "officiel"})
    elsewhere = reports.create(db_session, AUTRE_ECOLE, {"seasonId": 2, "name": "D", "state": "officiel"})
    reports.update(db_session, TRESORIER, second["id"], {"name": "B", "state": "officiel"})
    assert {r["name"]: r["state"] for r in reports.list(db_session, TRESORIER, 2)} == {"A": "valide", "B": "officiel"}
    assert reports.get(db_session, TRESORIER, other["id"])["state"] == "officiel"
    assert first["state"] == "officiel"
    # Une autre école ne voit ni ne touche ces bilans.
    assert reports.get(db_session, AUTRE_ECOLE, elsewhere["id"])["state"] == "officiel"
    assert reports.counts(db_session, AUTRE_ECOLE) == {2: 1}
    with pytest.raises(LookupError):
        reports.get(db_session, AUTRE_ECOLE, first["id"])


def test_report_validation(db_session, finances, costs):
    reports = make_reports(finances, FakeAnalyst(), costs)
    for data in ({"seasonId": 2, "name": " "}, {"seasonId": 2, "name": "X", "state": "final"}, {"seasonId": 2, "name": "X", "model": "gpt"}, {"seasonId": 999, "name": "X"}):
        with pytest.raises(ReportError):
            reports.create(db_session, TRESORIER, data)
    with pytest.raises(PermissionError):
        reports.create(db_session, Member(person_id=3, org_id=1, name="Margot"), {"seasonId": 2, "name": "X"})


def test_cost_in_dollars():
    class Usage:
        input_tokens = 30_000
        output_tokens = 4_000
        cache_creation_input_tokens = 0
        cache_read_input_tokens = 0

    # Sonnet : 30k × 2 $ + 4k × 10 $ par million = 0,10 $.
    assert cost_usd("claude-sonnet-5-5", Usage()) == pytest.approx(0.10)
    assert cost_usd("claude-opus-4-8", Usage()) == pytest.approx(0.15 + 0.10)


@pytest.mark.rbac_reel
def test_report_routes_and_downloads(client, db_session, ecole, monkeypatch):
    from app import main

    monkeypatch.setattr(main.finances_reports, "analyst", FakeAnalyst({"VIR PIZZA AG 29 NOV": "Réception AG"}))
    monkeypatch.setattr(main.finances_reports, "background", False)
    tresorier = entetes_session(ecole["tresorier"])
    files = [("files", (name, data, "application/pdf")) for name, data in statements_for_reports()]
    assert client.post("/finances/import", files=files, headers=tresorier).status_code == 200
    saison = client.get("/finances/seasons", headers=tresorier).json()["seasons"][0]["id"]

    listing = client.get("/finances/reports", params={"seasonId": saison}, headers=tresorier).json()
    assert [m["label"] for m in listing["models"]] == ["Haiku 5.5", "Sonnet 5.5", "Opus 5.5", "Fable 5.1"]
    assert listing["reports"] == [] and listing["counts"] == {}

    created = client.post("/finances/reports", json={"seasonId": saison, "name": "Bilan"}, headers=tresorier)
    assert created.status_code == 201, created.text
    report_id = created.json()["id"]
    assert client.get(f"/finances/reports/{report_id}/download", headers=tresorier).status_code == 400
    run = client.post(f"/finances/reports/{report_id}/run", json={"model": "claude-haiku-5-5", "prompt": "Court"}, headers=tresorier).json()
    assert run["status"] == "idle" and run["result"]["verification"]["ok"]

    xlsx = client.get(f"/finances/reports/{report_id}/download", params={"format": "xlsx"}, headers=tresorier)
    assert xlsx.status_code == 200 and xlsx.content[:2] == b"PK"
    pdf = client.get(f"/finances/reports/{report_id}/download", params={"format": "pdf"}, headers=tresorier)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"

    assert client.put(f"/finances/reports/{report_id}", json={"name": "Bilan", "state": "nul"}, headers=tresorier).status_code == 400
    assert client.get(f"/finances/reports/{report_id}", headers=entetes_session(ecole["admin"])).status_code == 403
    assert client.delete(f"/finances/reports/{report_id}", headers=tresorier).status_code == 204
    assert client.get(f"/finances/reports/{report_id}", headers=tresorier).status_code == 404
