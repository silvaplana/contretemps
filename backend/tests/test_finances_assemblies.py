"""Module finances, sous-module Assemblée générale (spec/modules/financier.md
§5) : choix du bilan et du PowerPoint modèle, remplissage du PowerPoint avec
le texte du modèle de langage (simulé ici), surlignage de « À compléter »,
garde-fou sur les montants, les 3 fichiers d'une AG, étanchéité entre écoles,
routes (`rbac_reel`)."""

import io

import pytest
from conftest import entetes_session
from pptx import Presentation
from pptx.oxml.ns import qn
from test_finances import AUTRE_ECOLE, SEASONS, TRESORIER, ecole, statements_for_reports  # noqa: F401 - fixtures

from finances import AssemblyError, GeneralAssemblies, Member, Season
from finances.ai import AnalysisError
from finances.assembly_ai import Draft
from finances import slides as slides_module
from finances.slides import amounts_in, check_amounts, outline, texts

RESULT = {
    "start": "2025-07-01",
    "end": "2026-06-30",
    "cutoff": "2026-06-30",
    "opening": 4922.56,
    "closing": 9716.86,
    "income": [{"category": "Cotisations", "amount": 11945.0}, {"category": "Clôture compte", "amount": 3290.74}],
    "expense": [{"category": "Salaires", "amount": 5905.0}],
    "totalIncome": 15718.28,
    "totalExpense": 10923.98,
    "result": 4794.30,
    "net": {"Cotisations": 11945.0, "Salaires": -5905.0},
    "verification": {"ok": True},
    "analysis": ["Ligne 1"],
    "previous": {
        "season": "2024-2025",
        "opening": 3000.0,
        "closing": 4922.56,
        "totalIncome": 9517.0,
        "totalExpense": 8288.0,
        "result": 1229.0,
        "net": {},
    },
}
SEASONS_WITH_MEMBERS = [Season(s.id, s.name, s.start_date, s.end_date, s.current, members=40 + s.id) for s in SEASONS]


def make_pptx(path, title="Résumé exécutif 2024/2025", lines=("Résultat global : +1507 €", "Cotisation : 300 €")):
    presentation = Presentation()
    first = presentation.slides.add_slide(presentation.slide_layouts[0])
    first.shapes.title.text = "Assemblée Générale\vBilan saison 2024-2025"
    first.placeholders[1].text = "Date : 04/07/2025"
    slide = presentation.slides.add_slide(presentation.slide_layouts[1])
    slide.shapes.title.text = title
    body = slide.placeholders[1].text_frame
    body.text = lines[0]
    for line in lines[1:]:
        paragraph = body.add_paragraph()
        paragraph.text = line
        paragraph.level = 1
    presentation.save(str(path))
    return path


class FakeWriter:
    """Modèle simulé : réécrit la diapo 2 (titre et texte) et la date."""

    def __init__(self, error=None, amount="4 794 €"):
        self.error = error
        self.amount = amount
        self.calls = []

    def write(self, model, data, prompt):
        self.calls.append((model, data, prompt))
        if self.error:
            raise AnalysisError(self.error, cost=0.02)
        zones = {z["role"]: z["zone"] for z in data["modele"][1]["zones"]}
        date_zone = data["modele"][0]["zones"][1]["zone"]
        return Draft(
            zones=[
                {"diapo": 2, "zone": zones["titre"], "paragraphes": [{"niveau": 0, "texte": "Résumé exécutif 2025/2026"}]},
                {
                    "diapo": 2,
                    "zone": zones["texte"],
                    "paragraphes": [
                        {"niveau": 0, "texte": f"Résultat global : +{self.amount}"},
                        {"niveau": 1, "texte": "Cotisation : À compléter"},
                    ],
                },
                {"diapo": 1, "zone": date_zone, "paragraphes": [{"niveau": 0, "texte": "Date : À compléter"}]},
                {"diapo": 9, "zone": 99, "paragraphes": [{"niveau": 0, "texte": "zone inconnue"}]},
            ],
            summary=["Diapos du trésorier remplies."],
            model=model,
            served_by="claude-sonnet-5-5",
            cost=0.12,
        )


class Reports:
    """Bilans simulés (FinancialReports.list / get), par école."""

    def __init__(self):
        self.items = {
            (1, 2): [
                {"id": 10, "name": "Bilan brouillon", "state": "brouillon", "hasResult": True},
                {"id": 11, "name": "Bilan officiel", "state": "officiel", "hasResult": True},
                {"id": 12, "name": "Bilan vide", "state": "valide", "hasResult": False},
            ]
        }

    def list(self, db, member, season_id):
        return self.items.get((member.org_id, season_id), [])

    def get(self, db, member, report_id):
        item = next(r for rs in self.items.values() for r in rs if r["id"] == report_id)
        return {**item, "result": RESULT}


@pytest.fixture
def setup(db_session, tmp_path):
    costs = []
    writer = FakeWriter()
    reports = Reports()
    client = GeneralAssemblies(
        storage_dir=tmp_path / "ag",
        seasons=lambda db, org_id: SEASONS_WITH_MEMBERS,
        reports=reports.list,
        report=reports.get,
        note_cost=lambda db, org_id, cost, detail: costs.append((org_id, cost)),
        writer=writer,
        background=False,
    )
    client.set_template(TRESORIER, make_pptx(tmp_path / "modele.pptx").read_bytes())
    return client, writer, reports, costs, tmp_path


def test_amounts_in():
    assert amounts_in("15 718 € et 4 794,36 € puis +1507€, 3.290,74 euros, saison 2025-2026, 50 inscrits") == [
        15718.0,
        4794.36,
        1507.0,
        3290.74,
    ]


def test_check_amounts_flags_unknown_amounts():
    zones = [{"diapo": 7, "paragraphes": [{"texte": "Résultat : +4 794 € ; cotisation 300 €"}]}]
    assert check_amounts(zones, {4794.30}) == ["Diapo 7 : 300 € ne vient pas du bilan, à vérifier."]


def test_outline_skips_empty_zones(tmp_path):
    path = make_pptx(tmp_path / "m.pptx")
    zones = outline(path)[1]["zones"]
    assert [z["role"] for z in zones] == ["titre", "texte"]
    assert zones[1]["paragraphes"][1] == {"niveau": 1, "texte": "Cotisation : 300 €"}


def test_run_fills_the_template_with_the_official_report(setup, db_session):
    client, writer, _, costs, _ = setup
    assembly = client.create(db_session, TRESORIER, {"seasonId": 2, "name": "AG 2026", "model": "claude-haiku-5-5", "prompt": "Ton simple"})
    done = client.run(db_session, TRESORIER, assembly["id"], {})

    assert done["status"] == "idle", done["error"]
    assert done["hasPpt"] is True
    # Le modèle par défaut (modèle général) est devenu le modèle de l'AG.
    assert [kind for kind, file in done["files"].items() if file] == ["modele", "genere"]
    assert done["files"]["modele"]["source"] == "Pris par défaut, faute de modèle choisi : Modèle général"
    result = done["result"]
    assert result["report"]["name"] == "Bilan officiel"
    assert result["template"]["kind"] == "uploaded"
    assert result["changedSlides"] == [1, 2]
    assert result["warnings"] == []
    assert result["summary"] == ["Diapos du trésorier remplies."]
    assert done["aiCostUsd"] == pytest.approx(0.12)
    assert costs == [(1, 0.12)]

    model, data, prompt = writer.calls[0]
    assert (model, prompt) == ("claude-haiku-5-5", "Ton simple")
    assert data["saison"] == "2025-2026" and data["saisonSuivante"] == "2026-2027"
    assert data["bilan"]["totalRecettes"] == 15718.28
    assert data["inscrits"] == [{"saison": "2024-2025", "inscrits": 41}, {"saison": "2025-2026", "inscrits": 42}]
    assert data["modele"][0]["zones"][0]["paragraphes"][0]["texte"] == "Assemblée Générale\nBilan saison 2024-2025"

    path, filename = client.file_path(db_session, TRESORIER, assembly["id"])
    assert filename == "AG-2025-2026-AG 2026.pptx"
    slide = texts(path)[1]
    assert slide["title"] == "Résumé exécutif 2025/2026"
    assert slide["lines"] == [
        {"level": 0, "text": "Résultat global : +4 794 €"},
        {"level": 1, "text": "Cotisation : À compléter"},
    ]
    # « À compléter » dans un morceau à part, surligné en jaune.
    body = Presentation(str(path)).slides[1].placeholders[1].text_frame.paragraphs[1]
    highlighted = [r.text for r in body.runs if r._r.find(qn("a:rPr") + "/" + qn("a:highlight")) is not None]
    assert highlighted == ["À compléter"]


def test_run_warns_about_amounts_not_in_the_report(setup, db_session):
    client, writer, *_ = setup
    writer.amount = "1 507 €"
    assembly = client.create(db_session, TRESORIER, {"seasonId": 2, "name": "AG"})
    assert client.run(db_session, TRESORIER, assembly["id"], {})["result"]["warnings"] == ["Diapo 2 : 1 507 € ne vient pas du bilan, à vérifier."]
    # Un montant donné dans les consignes est accepté.
    assert client.run(db_session, TRESORIER, assembly["id"], {"prompt": "Le résultat de l'an dernier était 1507 €"})["result"]["warnings"] == []
    # Le nouveau PowerPoint a remplacé le précédent : un seul fichier par sorte.
    folder = client.storage / "1" / str(assembly["id"])
    assert len(list(folder.glob("v*.pptx"))) == 2


def test_run_needs_a_report_and_a_template(setup, db_session):
    client, _, reports, _, _ = setup
    assembly = client.create(db_session, TRESORIER, {"seasonId": 1, "name": "AG 2025"})
    with pytest.raises(AssemblyError, match="Bilan"):
        client.run(db_session, TRESORIER, assembly["id"], {})
    reports.items[(1, 1)] = [{"id": 20, "name": "B", "state": "valide", "hasResult": True}]
    client._template_path(1).unlink()
    with pytest.raises(AssemblyError, match="PowerPoint modèle"):
        client.run(db_session, TRESORIER, assembly["id"], {})


def test_previous_official_assembly_is_the_template(setup, db_session):
    client, _, reports, _, tmp_path = setup
    reports.items[(1, 1)] = [{"id": 20, "name": "B", "state": "valide", "hasResult": True}]
    previous = client.create(db_session, TRESORIER, {"seasonId": 1, "name": "AG 2025", "state": "officiel"})
    client.upload(db_session, TRESORIER, previous["id"], make_pptx(tmp_path / "ag2025.pptx", title="Résumé 2025").read_bytes(), "ag2025.pptx")

    options = client.options(db_session, TRESORIER, 2)
    assert options["report"] == {"id": 11, "name": "Bilan officiel", "state": "officiel"}
    assert options["template"] == {"kind": "previous", "name": "AG officielle 2024-2025 (AG 2025)"}
    assembly = client.create(db_session, TRESORIER, {"seasonId": 2, "name": "AG 2026"})
    assert client.run(db_session, TRESORIER, assembly["id"], {})["result"]["template"]["kind"] == "previous"


def test_own_model_is_used_instead_of_the_default(setup, db_session):
    client, writer, _, _, tmp_path = setup
    assembly = client.create(db_session, TRESORIER, {"seasonId": 2, "name": "AG 2026"})
    client.set_model(db_session, TRESORIER, assembly["id"], make_pptx(tmp_path / "ex.pptx", title="Exemple du club").read_bytes(), "ex.pptx")

    done = client.run(db_session, TRESORIER, assembly["id"], {})

    assert done["result"]["template"] == {"kind": "own", "name": "ex.pptx"}
    assert writer.calls[0][1]["modele"][1]["zones"][0]["paragraphes"][0]["texte"] == "Exemple du club"
    # Le modèle reste celui choisi, et un PowerPoint modifié ne le remplace pas.
    client.upload(db_session, TRESORIER, assembly["id"], make_pptx(tmp_path / "m.pptx", title="Retouché").read_bytes(), "m.pptx")
    files = client.get(db_session, TRESORIER, assembly["id"])["files"]
    assert [files[kind]["filename"] for kind in ("modele", "genere", "modifie")] == ["ex.pptx", "AG-2025-2026-AG 2026.pptx", "m.pptx"]
    assert texts(client.file_path(db_session, TRESORIER, assembly["id"])[0])[1]["title"] == "Retouché"


def test_one_official_per_season_delete_and_isolation(setup, db_session):
    client, *_ = setup
    first = client.create(db_session, TRESORIER, {"seasonId": 2, "name": "A", "state": "officiel"})
    client.run(db_session, TRESORIER, first["id"], {})
    second = client.create(db_session, TRESORIER, {"seasonId": 2, "name": "B", "state": "officiel"})
    assert client.get(db_session, TRESORIER, first["id"])["state"] == "valide"
    assert client.get(db_session, TRESORIER, second["id"])["state"] == "officiel"
    # Une autre école ne voit rien de tout ça, ni ses fichiers ni son modèle général.
    assert client.list(db_session, AUTRE_ECOLE, 2) == []
    assert client.counts(db_session, AUTRE_ECOLE) == {}
    assert client.options(db_session, AUTRE_ECOLE, 2)["templateUploaded"] is False
    assert client.model_sources(db_session, AUTRE_ECOLE) == []
    with pytest.raises(LookupError):
        client.get(db_session, AUTRE_ECOLE, first["id"])
    with pytest.raises(PermissionError):
        client.list(db_session, Member(person_id=3, org_id=1, name="Margot"), 2)
    folder = client.storage / "1" / str(first["id"])
    assert folder.exists()
    client.delete(db_session, TRESORIER, first["id"])
    assert not folder.exists()
    assert [a["name"] for a in client.list(db_session, TRESORIER, 2)] == ["B"]


def test_error_keeps_cost_and_no_file(setup, db_session):
    client, writer, _, costs, _ = setup
    writer.error = "La préparation de cette AG a été refusée."
    assembly = client.create(db_session, TRESORIER, {"seasonId": 2, "name": "AG"})
    done = client.run(db_session, TRESORIER, assembly["id"], {})
    assert (done["status"], done["error"]) == ("error", "La préparation de cette AG a été refusée.")
    assert done["hasPpt"] is False
    assert costs == [(1, 0.02)]


@pytest.mark.rbac_reel
def test_routes_upload_download_and_slides(client, db_session, ecole, monkeypatch, tmp_path):  # noqa: F811
    from app import main
    from test_finances import FakeAnalyst

    monkeypatch.setattr(slides_module, "soffice", lambda: None)
    monkeypatch.setattr(main.finances_reports, "analyst", FakeAnalyst())
    monkeypatch.setattr(main.finances_reports, "background", False)
    monkeypatch.setattr(main.finances_assemblies, "storage", tmp_path / "ag")
    monkeypatch.setattr(main.finances_assemblies, "writer", FakeWriter())
    monkeypatch.setattr(main.finances_assemblies, "background", False)
    tresorier = entetes_session(ecole["tresorier"])

    # Un bilan calculé pour la saison, puis le modèle général de l'école.
    files = [("files", (name, data, "application/pdf")) for name, data in statements_for_reports()]
    assert client.post("/finances/import", files=files, headers=tresorier).status_code == 200
    saison = client.get("/finances/seasons", headers=tresorier).json()["seasons"][0]["id"]
    report = client.post("/finances/reports", json={"seasonId": saison, "name": "Bilan"}, headers=tresorier).json()
    assert client.post(f"/finances/reports/{report['id']}/run", json={}, headers=tresorier).json()["status"] == "idle"
    template = make_pptx(tmp_path / "modele.pptx").read_bytes()
    assert client.post("/finances/assemblies/template", files={"file": ("modele.pptx", template)}, headers=tresorier).status_code == 200

    listing = client.get("/finances/assemblies", params={"seasonId": saison}, headers=tresorier).json()
    assert listing["templateUploaded"] is True and listing["report"]["name"] == "Bilan"
    created = client.post("/finances/assemblies", json={"seasonId": saison, "name": "AG 2026"}, headers=tresorier)
    assert created.status_code == 201, created.text
    assembly_id = created.json()["id"]
    run = client.post(f"/finances/assemblies/{assembly_id}/run", json={"model": "claude-fable-5-1"}, headers=tresorier).json()
    assert run["status"] == "idle", run["error"]
    assert run["model"] == "claude-fable-5-1"

    sent = make_pptx(tmp_path / "modifie.pptx", title="Ma version").read_bytes()
    response = client.post(f"/finances/assemblies/{assembly_id}/upload", files={"file": ("ma-version.pptx", sent)}, headers=tresorier)
    assert [kind for kind, file in response.json()["files"].items() if file] == ["modele", "genere", "modifie"]

    download = client.get(f"/finances/assemblies/{assembly_id}/download", headers=tresorier)
    assert download.status_code == 200
    assert texts(io.BytesIO(download.content))[1]["title"] == "Ma version"
    first = client.get(f"/finances/assemblies/{assembly_id}/download", params={"kind": "genere"}, headers=tresorier)
    assert texts(io.BytesIO(first.content))[1]["title"] == "Résumé exécutif 2025/2026"

    preview = client.get(f"/finances/assemblies/{assembly_id}/files/modifie/slides", headers=tresorier).json()
    assert preview["thumbnails"] is False
    assert [s["title"] for s in preview["slides"]] == ["Assemblée Générale Bilan saison 2024-2025", "Ma version"]
    assert client.get(f"/finances/assemblies/{assembly_id}/files/inconnu/slides", headers=tresorier).status_code == 404

    bad = client.post(f"/finances/assemblies/{assembly_id}/upload", files={"file": ("x.pptx", b"pas un ppt")}, headers=tresorier)
    assert bad.status_code == 400
    listing = client.get("/finances/assemblies", params={"seasonId": saison}, headers=tresorier).json()
    assert listing["counts"] == {str(saison): 1}
    assert [a["hasPpt"] for a in listing["assemblies"]] == [True]

    # Modèle d'une autre AG : fichier de l'ordinateur, ou PowerPoint d'une AG.
    other = client.post("/finances/assemblies", json={"seasonId": saison, "name": "Essai"}, headers=tresorier).json()
    sources = client.get("/finances/assemblies/model-sources", params={"exclude": other["id"]}, headers=tresorier).json()
    assert [(x["assemblyId"], x["kind"]) for x in sources] == [(assembly_id, "modifie"), (assembly_id, "genere"), (assembly_id, "modele"), (None, "general")]
    assert sources[0]["label"].endswith("AG 2026 : PowerPoint modifié")
    copied = client.put(f"/finances/assemblies/{other['id']}/model", json={"sourceId": assembly_id, "kind": "modifie"}, headers=tresorier)
    assert copied.json()["files"]["modele"]["filename"] == "ma-version.pptx"
    assert client.put(f"/finances/assemblies/{other['id']}/model", json={"sourceId": other["id"], "kind": "modele"}, headers=tresorier).status_code == 400

    admin = entetes_session(ecole["admin"])
    assert client.get(f"/finances/assemblies/{assembly_id}", headers=admin).status_code == 403
    assert client.delete(f"/finances/assemblies/{assembly_id}", headers=tresorier).status_code == 204
    assert client.get(f"/finances/assemblies/{assembly_id}", headers=tresorier).status_code == 404
