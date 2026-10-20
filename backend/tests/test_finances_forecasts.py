"""Module finances, sous-module Prévisionnel (spec/modules/financier.md §6) :
données préparées pour la formule, vérification et exécution à part de la
formule écrite par le modèle (simulé ici), curseurs, date de départ, coût,
étanchéité entre écoles, routes et téléchargements."""

from datetime import date

import pymupdf
import pytest
from conftest import entetes_session
from test_finances import (  # noqa: F401 - fixtures
    AUTRE_ECOLE,
    SEASONS,
    TRESORIER,
    ecole,
    statements_for_reports,
)

from finances import ForecastError, Forecasts, Member, forecast_data, forecast_exports
from finances.ai import AnalysisError
from finances.forecast_ai import Formula, defaults
from finances.sandbox import FormulaError, check, run
from finances.service import Finances

TODAY = date(2026, 10, 6)

CODE = '''
import math

def prevoir(donnees, p):
    """Salaire chaque mois, cotisations des nouveaux inscrits."""
    solde = donnees["soldeDepart"]
    points = []
    for semaine in donnees["semaines"]:
        for mois in semaine["mois_commences"]:
            solde -= p["salaire"]
            solde += p["nouveaux"] * 10
        points.append({"date": semaine["date"], "solde": round(solde, 2)})
    return points
'''
PARAMETERS = [
    {"name": "salaire", "label": "Salaire mensuel", "min": 0, "max": 2000, "default": 1000, "step": 10, "unit": "€"},
    {"name": "nouveaux", "label": "Nouveaux inscrits", "min": 0, "max": 20, "default": 5, "step": 1, "unit": ""},
]
# Solde de tous les comptes au 31/08/2026 (dernier jour des relevés) et au
# 30/06/2026 (début de la saison 2026-2027) : courant 12 603,94 + livret 3 067,94.
BALANCE = 15671.88


class FakeCoder:
    """Modèle simulé : renvoie toujours la même formule, exécutée pour de vrai."""

    def __init__(self, code=CODE, error=None):
        self.code = code
        self.error = error
        self.calls = []

    def write(self, model, data, prompt):
        self.calls.append((model, data, prompt))
        if self.error:
            raise AnalysisError(self.error, cost=0.01)
        return Formula(
            code=self.code,
            explanation="Salaire chaque mois.",
            parameters=PARAMETERS,
            balances=run(self.code, data, defaults(PARAMETERS)),
            model=model,
            served_by="claude-sonnet-5-5",
            cost=0.05,
        )


@pytest.fixture
def finances():
    return Finances()


@pytest.fixture
def ledger_db(db_session, finances):
    finances.import_files(db_session, TRESORIER, statements_for_reports())
    return db_session


@pytest.fixture
def costs():
    return []


def make_forecasts(finances, coder, costs):
    return Forecasts(
        ledger=finances.get_ledger,
        seasons=lambda db, org_id: SEASONS,
        note_cost=lambda db, org_id, cost, detail: costs.append((org_id, cost, detail)),
        today=lambda: TODAY,
        coder=coder,
        background=False,
    )


# ----- formule -----


@pytest.mark.parametrize(
    "code, message",
    [
        ("import os\ndef prevoir(d, p):\n    return []", "Import interdit : os"),
        ("def prevoir(d, p):\n    return open('/etc/passwd').read()", "Nom interdit"),
        ("def prevoir(d, p):\n    return ().__class__", "Attribut interdit"),
        ("def prevoir(d, p):\n    g = (x for x in [1])\n    return g.gi_frame", "Attribut interdit dans la formule : gi_frame"),
        ("def prevoir(d, p):\n    return '{0.real}'.format(1)", "Attribut interdit dans la formule : format"),
        ("def calcul(d, p):\n    return []", "prevoir"),
        ("def prevoir(d, p)\n    return []", "illisible"),
    ],
)
def test_check_refuses_dangerous_code(code, message):
    with pytest.raises(FormulaError, match=message):
        check(code)


def test_run_executes_in_separate_process():
    data = {"soldeDepart": 1000.0, "semaines": [{"date": "2026-10-13", "mois_commences": []}, {"date": "2026-10-20", "mois_commences": []}]}
    code = "import math\ndef prevoir(d, p):\n    return [d['soldeDepart'] + math.floor(p['x']) * i for i in range(len(d['semaines']))]"
    assert run(code, data, {"x": 10.7}) == [1000.0, 1010.0]


def test_run_reports_errors_and_wrong_sizes():
    data = {"soldeDepart": 0.0, "semaines": [{"date": "2026-10-13", "mois_commences": []}]}
    with pytest.raises(FormulaError, match="ZeroDivisionError"):
        run("def prevoir(d, p):\n    return [1 / 0]", data, {})
    with pytest.raises(FormulaError, match="une valeur par semaine"):
        run("def prevoir(d, p):\n    return [1, 2]", data, {})
    with pytest.raises(FormulaError, match="Import interdit : socket"):
        run("def prevoir(d, p):\n    import socket\n    return [0]", data, {})


# Formule hostile : par un générateur, remonte aux variables du programme
# lanceur (sys, builtins), puis tente ACTION avec ce qu'elle y trouve.
ESCAPE = """
def prevoir(donnees, p):
    cadre = [0]
    def lire():
        g = (g.gi_frame.f_back.f_back for x in [1])
        for f in g:
            cadre[0] = f
    lire()
    f = cadre[0]
    while "sys" not in f.f_globals:
        f = f.f_back
    systeme = f.f_globals["sys"]
    integrees = f.f_globals["builtins"]
    ACTION
    return [1.0]
"""


@pytest.mark.parametrize(
    "action",
    ['integrees.open("/etc/hostname").read()', 'systeme.modules["os"].system("true")', 'integrees.__import__("socket")'],
)
def test_escaped_formula_can_do_nothing(monkeypatch, action):
    """Même si la vérification du code était contournée, le processus de
    calcul refuse fichiers, programmes, réseau et imports."""
    monkeypatch.setattr("finances.sandbox.check", lambda code: None)
    data = {"soldeDepart": 0.0, "semaines": [{"date": "2026-10-13", "mois_commences": []}]}
    with pytest.raises(FormulaError, match="Opération interdite dans la formule"):
        run(ESCAPE.replace("ACTION", action), data, {})


def test_escape_is_refused_by_check():
    with pytest.raises(FormulaError, match="Attribut interdit"):
        check(ESCAPE.replace("ACTION", "pass"))


def test_run_stops_endless_formula(monkeypatch):
    monkeypatch.setattr("finances.sandbox.TIMEOUT", 2)
    data = {"soldeDepart": 0.0, "semaines": [{"date": "2026-10-13", "mois_commences": []}]}
    with pytest.raises(FormulaError):
        run("def prevoir(d, p):\n    while True:\n        pass", data, {})


# ----- données -----


def test_weeks_mark_new_months():
    weeks = forecast_data.weeks("2026-10-06", "2026-11-10")
    assert [w["date"] for w in weeks] == ["2026-10-13", "2026-10-20", "2026-10-27", "2026-11-03", "2026-11-10"]
    assert [w["mois_commences"] for w in weeks] == [[], [], [], ["2026-11"], []]


def test_build_data(ledger_db, finances):
    season = {"name": "2026-2027", "startDate": "2026-07-01", "endDate": "2027-06-30"}
    data = forecast_data.build(finances.get_ledger(ledger_db, TRESORIER), season, "2026-08-31", None)
    assert data["soldeDepart"] == BALANCE and data["soldeDebutSaison"] == BALANCE
    assert data["moisEnCours"] == {"mois": "2026-08", "dejaPasseParCategorie": {}}
    assert len(data["douzeDerniersMois"]) == 12
    # Septembre 2025 à août 2026 : Stripe 6000 et FFST −500 en septembre, pizza AG en décembre, clôture en juin, intérêts.
    assert data["moyennesMensuelles"]["Cotisations en ligne"] == 500.0
    assert data["adherents"] is None
    assert data["semaines"][-1]["date"] == "2027-06-30"


# ----- prévisionnels -----


def test_run_writes_formula_and_points(ledger_db, finances, costs):
    coder = FakeCoder()
    forecasts = make_forecasts(finances, coder, costs)
    created = forecasts.create(ledger_db, TRESORIER, {"seasonId": 3, "name": "Prudent"})
    assert created["result"] is None and created["startDate"] is None and created["model"] == "claude-sonnet-5-5"

    done = forecasts.run(ledger_db, TRESORIER, created["id"], {"prompt": "Salaire 1000 €", "model": "claude-haiku-5-5"})
    assert done["status"] == "idle", done["error"]
    model, data, prompt = coder.calls[0]
    assert (model, prompt) == ("claude-haiku-5-5", "Salaire 1000 €")
    # Date de départ : dernier jour connu des comptes (au plus aujourd'hui).
    assert data["dateDepart"] == "2026-08-31"
    points = done["result"]["points"]
    assert points[0] == {"date": "2026-08-31", "solde": BALANCE}
    # 10 mois commencés (septembre à juin) : −1000 + 50 chacun.
    assert points[-1] == {"date": "2027-06-30", "solde": round(BALANCE - 10 * 950, 2)}
    assert done["params"] == {"salaire": 1000, "nouveaux": 5}
    assert done["endBalance"] == points[-1]["solde"]
    assert done["aiCostUsd"] == pytest.approx(0.05)
    assert costs == [(1, 0.05, "Prévisionnel Prudent")]


def test_sliders_replay_formula_and_are_kept(ledger_db, finances, costs):
    forecasts = make_forecasts(finances, FakeCoder(), costs)
    fid = forecasts.create(ledger_db, TRESORIER, {"seasonId": 3, "name": "Prudent"})["id"]
    forecasts.run(ledger_db, TRESORIER, fid, {})
    moved = forecasts.set_params(ledger_db, TRESORIER, fid, {"salaire": 500, "nouveaux": 99})
    # nouveaux ramené à son maximum (20).
    assert moved["params"] == {"salaire": 500.0, "nouveaux": 20.0}
    assert moved["result"]["points"][-1]["solde"] == round(BALANCE + 10 * (200 - 500), 2)
    # Nouveau calcul : les curseurs restent à leur position.
    again = forecasts.run(ledger_db, TRESORIER, fid, {})
    assert again["params"] == {"salaire": 500.0, "nouveaux": 20.0}
    assert again["aiCostUsd"] == pytest.approx(0.10)
    with pytest.raises(ForecastError):
        forecasts.set_params(ledger_db, TRESORIER, fid, {"salaire": "beaucoup"})


def test_start_date_to_test_on_past_season(ledger_db, finances, costs):
    forecasts = make_forecasts(finances, FakeCoder(), costs)
    with pytest.raises(ForecastError, match="dans la saison"):
        forecasts.create(ledger_db, TRESORIER, {"seasonId": 2, "name": "Test", "startDate": "2026-07-01"})
    fid = forecasts.create(ledger_db, TRESORIER, {"seasonId": 2, "name": "Test"})["id"]
    # Saison terminée : une date de départ est obligatoire.
    with pytest.raises(ForecastError, match="Saison terminée"):
        forecasts.run(ledger_db, TRESORIER, fid, {})
    done = forecasts.run(ledger_db, TRESORIER, fid, {"startDate": "2026-01-01"})
    assert done["startDate"] == "2026-01-01"
    # Courant 5000 − 1200 + 200 + 6000 − 500 − 186,80, livret 3067,94.
    assert done["result"]["points"][0] == {"date": "2026-01-01", "solde": 12381.14}


def test_error_is_shown_and_charged(ledger_db, finances, costs):
    forecasts = make_forecasts(finances, FakeCoder(error="L'écriture de ce prévisionnel a été refusée."), costs)
    fid = forecasts.create(ledger_db, TRESORIER, {"seasonId": 3, "name": "Essai"})["id"]
    failed = forecasts.run(ledger_db, TRESORIER, fid, {})
    assert failed["status"] == "error" and failed["error"] == "L'écriture de ce prévisionnel a été refusée."
    assert failed["aiCostUsd"] == pytest.approx(0.01) and costs == [(1, 0.01, "Prévisionnel Essai")]
    # Formule qui échoue à l'exécution : erreur affichable, rien de facturé.
    broken = make_forecasts(finances, FakeCoder(code="def prevoir(d, p):\n    return [1 / 0] * len(d['semaines'])"), costs)
    with pytest.raises(FormulaError):
        broken.coder.write("claude-haiku-5-5", {"soldeDepart": 0.0, "semaines": [{"date": "2026-10-13", "mois_commences": []}]}, "")


def test_validation_and_isolation_between_schools(db_session, finances, costs):
    forecasts = make_forecasts(finances, FakeCoder(), costs)
    for data in ({"seasonId": 3, "name": " "}, {"seasonId": 3, "name": "X", "state": "final"}, {"seasonId": 3, "name": "X", "model": "gpt"}, {"seasonId": 999, "name": "X"}, {"seasonId": 3, "name": "X", "startDate": "hier"}):
        with pytest.raises(ForecastError):
            forecasts.create(db_session, TRESORIER, data)
    with pytest.raises(PermissionError):
        forecasts.create(db_session, Member(person_id=3, org_id=1, name="Margot"), {"seasonId": 3, "name": "X"})
    # Plusieurs officiels par saison ; chaque école ne voit que les siens.
    forecasts.create(db_session, TRESORIER, {"seasonId": 3, "name": "A", "state": "officiel"})
    mine = forecasts.create(db_session, TRESORIER, {"seasonId": 3, "name": "B", "state": "officiel"})
    forecasts.create(db_session, AUTRE_ECOLE, {"seasonId": 3, "name": "C"})
    assert [f["state"] for f in forecasts.list(db_session, TRESORIER, 3)] == ["officiel", "officiel"]
    assert forecasts.counts(db_session, AUTRE_ECOLE) == {3: 1}
    from finances import ForecastNotFoundError

    for action in (forecasts.get, forecasts.delete):
        with pytest.raises(ForecastNotFoundError):
            action(db_session, AUTRE_ECOLE, mine["id"])


def test_export_keeps_only_chosen_seasons(ledger_db, finances, costs):
    """Image et PDF : les saisons comparées sont celles choisies à l'écran, et
    le contenu se limite au titre, aux hypothèses, aux soldes et au graphique."""
    forecasts = make_forecasts(finances, FakeCoder(), costs)
    created = forecasts.create(ledger_db, TRESORIER, {"seasonId": 3, "name": "Prévision"})
    forecasts.run(ledger_db, TRESORIER, created["id"], {})
    forecast = forecasts.get(ledger_db, TRESORIER, created["id"])
    ledger = finances.get_ledger(ledger_db, TRESORIER)
    previous = {"name": "2025-2026", "startDate": "2025-07-01", "endDate": "2026-06-30", "color": forecast_exports.SEASON_COLORS[0]}

    with_previous = forecast_exports.chart_svg(forecast, ledger, [previous])
    alone = forecast_exports.chart_svg(forecast, ledger, [])
    assert ">2025-2026<" in with_previous and ">2025-2026<" not in alone
    for text in ("Prévision — saison 2026-2027", "Solde au 01/07/2026", "Solde prévu au 30/06/2027", "Résultat prévu au 30/06/2027"):
        assert text in alone
    assert "Solde prévu" not in forecast_exports.chart_svg(forecast, ledger, [], header=False)

    with pytest.raises(ForecastError, match="Format inconnu"):
        forecasts.export(ledger_db, TRESORIER, created["id"], "xlsx")
    assert forecasts.export(ledger_db, TRESORIER, created["id"], "png")[1] == "image/png"
    pdf, media_type, name = forecasts.export(ledger_db, TRESORIER, created["id"], "pdf", [])
    assert media_type == "application/pdf" and name == f"previsionnel-2026-2027-{created['id']}.pdf"
    text = pymupdf.open(stream=pdf, filetype="pdf")[0].get_text()
    assert "Soldes et résultat" in text and "Formule" not in text


@pytest.mark.rbac_reel
def test_forecast_routes_and_downloads(client, db_session, ecole, monkeypatch):  # noqa: F811
    from app import main

    monkeypatch.setattr(main.finances_forecasts, "coder", FakeCoder())
    monkeypatch.setattr(main.finances_forecasts, "background", False)
    monkeypatch.setattr(main.finances_forecasts, "today", lambda: TODAY)
    tresorier = entetes_session(ecole["tresorier"])
    files = [("files", (name, data, "application/pdf")) for name, data in statements_for_reports()]
    assert client.post("/finances/import", files=files, headers=tresorier).status_code == 200
    saison = client.get("/finances/seasons", headers=tresorier).json()["seasons"][0]

    listing = client.get("/finances/forecasts", params={"seasonId": saison["id"]}, headers=tresorier).json()
    assert listing["defaultModel"] == "claude-sonnet-5-5" and listing["forecasts"] == [] and listing["counts"] == {}

    created = client.post("/finances/forecasts", json={"seasonId": saison["id"], "name": "Prudent", "prompt": "x"}, headers=tresorier)
    assert created.status_code == 201, created.text
    fid = created.json()["id"]
    assert client.get(f"/finances/forecasts/{fid}/download", headers=tresorier).status_code == 400
    # La saison de l'école de test est passée ou en cours selon la date : une date de départ dans la saison.
    run = client.post(f"/finances/forecasts/{fid}/run", json={"model": "claude-haiku-5-5", "startDate": saison["startDate"]}, headers=tresorier)
    assert run.status_code == 200 and run.json()["status"] == "idle", run.text
    assert client.put(f"/finances/forecasts/{fid}/params", json={"params": {"salaire": 800}}, headers=tresorier).json()["params"]["salaire"] == 800

    png = client.get(f"/finances/forecasts/{fid}/download", params={"format": "png"}, headers=tresorier)
    assert png.status_code == 200 and png.content[:4] == b"\x89PNG"
    pdf = client.get(f"/finances/forecasts/{fid}/download", params={"format": "pdf", "seasons": ""}, headers=tresorier)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"

    assert client.put(f"/finances/forecasts/{fid}", json={"name": "Prudent", "state": "nul"}, headers=tresorier).status_code == 400
    assert client.get(f"/finances/forecasts/{fid}", headers=entetes_session(ecole["admin"])).status_code == 403
    assert client.delete(f"/finances/forecasts/{fid}", headers=tresorier).status_code == 204
    assert client.get(f"/finances/forecasts/{fid}", headers=tresorier).status_code == 404
