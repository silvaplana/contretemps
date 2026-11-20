"""Rapport financier rédigé (financier.md §8.6) : le modèle écrit des repères,
l'appli place les montants ; un nombre écrit par le modèle est signalé ;
Word et PDF produits ; texte gardé et relu."""

import json
from types import SimpleNamespace

import pymupdf
import pytest
from docx import Document
from test_finances import TRESORIER
from test_finances_ag_documents import SEASON, world  # noqa: F401 - fixture

from finances import WrittenReports
from finances.written_report import figures, fill


class FakeStream:
    def __init__(self, draft):
        self.draft = draft

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get_final_message(self):
        usage = SimpleNamespace(input_tokens=1000, output_tokens=500, cache_read_input_tokens=0, cache_creation_input_tokens=0)
        return SimpleNamespace(
            model="claude-sonnet-5-5", stop_reason="end_turn", usage=usage,
            content=[SimpleNamespace(type="text", text=json.dumps(self.draft))],
        )


def fake_client(draft, seen):
    def stream(**params):
        seen.append(params)
        return FakeStream(draft)

    return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=stream)))


DRAFT = {
    "introduction": "Ce rapport couvre la saison.",
    "recettes": ["Les cotisations ont rapporté {{produits.706}} et les dons {{produits.756}}.", "Le gala a rapporté {{gala.ressources}}."],
    "depenses": ["La location de la salle a coûté {{charges.613}}, soit 1 600 € environ.", "Un prélèvement de {{charges.65900}} reste à classer ({{inconnu}})."],
    "points": ["Hausse de 12 % des fournitures."],
    "conclusion": "Nous présentons un résultat de {{resultat}} et une trésorerie de {{tresorerie}}.",
}


@pytest.fixture
def writer(world):
    _, _, documents = world
    seen = []
    stored = []
    w = WrittenReports(
        synthese=documents.synthese, seasons=lambda db, org: [SEASON], org_name=lambda db, org: "Contretemps",
        client=fake_client(DRAFT, seen), store=lambda db, m, path, files: stored.append((path, [n for n, _ in files])),
        note_cost=lambda db, org, cost, detail: seen.append(("cost", cost, detail)),
    )
    return w, seen, stored


def test_figures_and_fill():
    current = {
        "charges": [{"code": "61", "lines": [{"number": "613", "label": "Location", "amount": 1600.0}]}],
        "produits": [{"code": "70", "lines": [{"number": "706", "label": "Cotisations", "amount": 2298.0}]}],
        "totalCharges": 1600.0, "totalProduits": 2298.0, "result": 698.0, "treasuryTotal": 2148.0, "unpaidTotal": 0.0, "events": [],
    }
    previous = {**current, "charges": [{"code": "61", "lines": [{"number": "613", "label": "Location", "amount": 2000.0}]}]}
    f = figures(current, previous)
    assert f["charges.613"]["value"] == "1 600,00 €" and f["ecart.613"]["value"] == "−400,00 €" and f["pct.613"]["value"] == "-20,0 %"
    assert "precedent.totalCharges" in f and f["resultat"]["value"] == "698,00 €"
    text, warnings = fill("Location : {{charges.613}} ({{pct.613}}), {{rien}} ; environ 1 500 € et 7 %.", f)
    assert text == "Location : 1 600,00 € (-20,0 %), ; environ 1 500 € et 7 %."
    assert warnings == ["Repère inconnu « rien » effacé.", "1 500 € écrit par le modèle, à vérifier.", "« 7 % » écrit par le modèle, à vérifier."]


def test_write_places_the_figures_and_keeps_the_text(writer, db_session):
    w, seen, _ = writer
    result = w.write(db_session, TRESORIER, 1, SEASON, "Insiste sur le gala.", "claude-sonnet-5-5", ["Analyse du bilan."])
    params = seen[0]
    assert params["output_config"]["format"]["type"] == "json_schema"
    assert "Consignes du trésorier" in params["messages"][0]["content"] and "Analyse du bilan." in params["messages"][0]["content"]
    assert result["recettes"][0] == "Les cotisations ont rapporté 2 298,00 € et les dons 300,00 €."
    assert result["recettes"][1] == "Le gala a rapporté 150,00 €."
    assert result["depenses"][1] == "Un prélèvement de 12,00 € reste à classer ()."
    assert result["conclusion"] == "Nous présentons un résultat de 1 096,10 € et une trésorerie de 2 546,10 €."
    # 1 600 € écrit par le modèle = un chiffre connu : pas d'alerte ; 12 % et {{inconnu}} : alertes.
    assert result["warnings"] == ["Repère inconnu « inconnu » effacé.", "« 12 % » écrit par le modèle, à vérifier."]
    assert result["costUsd"] > 0 and seen[-1][0] == "cost" and "2025-2026" in seen[-1][2]
    again = w.get(db_session, 1)
    assert again["id"] == result["id"] and again["prompt"] == "Insiste sur le gala."
    assert w.get(db_session, 2) is None


def test_docx_and_pdf_are_produced_and_stored(writer, db_session):
    w, _, stored = writer
    w.write(db_session, TRESORIER, 1, SEASON, "", "claude-sonnet-5-5", [])
    content, name, media = w.produce(db_session, TRESORIER, 1, SEASON, "docx")
    assert name == "Rapport financier 2025-2026.docx" and "wordprocessingml" in media
    paragraphs = [p.text for p in Document(__import__("io").BytesIO(content)).paragraphs]
    assert paragraphs[0] == "Rapport financier de l'association Contretemps" and "A - Recettes" in paragraphs
    assert "Nous présentons un résultat de 1 096,10 € et une trésorerie de 2 546,10 €." in paragraphs
    content, name, media = w.produce(db_session, TRESORIER, 1, SEASON, "pdf")
    assert media == "application/pdf"
    text = "".join(p.get_text() for p in pymupdf.open(stream=content, filetype="pdf"))
    assert "B - Dépenses" in text and "1 096,10 €" in text
    assert stored == [(["AG"], ["Rapport financier 2025-2026.docx"]), (["AG"], ["Rapport financier 2025-2026.pdf"])]
    with pytest.raises(LookupError):
        w.produce(db_session, TRESORIER, 2, SEASON, "pdf")
    with pytest.raises(ValueError):
        w.produce(db_session, TRESORIER, 1, SEASON, "odt")


def test_in_docs_returns_the_stored_file_id(writer, db_session):
    w, _, stored = writer
    w.write(db_session, TRESORIER, 1, SEASON, "", "claude-sonnet-5-5", [])
    w.store = lambda db, member, path, files: stored.append((path, [n for n, _ in files])) or [7]
    assert w.in_docs(db_session, TRESORIER, 1, SEASON, "docx") == 7
    assert stored[-1] == (["AG"], ["Rapport financier 2025-2026.docx"])
    with pytest.raises(LookupError):
        w.in_docs(db_session, TRESORIER, 2, SEASON, "docx")


def scripted_client(responses, seen):
    """Un faux modèle qui rend, tour après tour, les blocs donnés."""
    class Stream:
        def __init__(self, message):
            self.message = message

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get_final_message(self):
            return self.message

    def stream(**params):
        seen.append(params)
        usage = SimpleNamespace(input_tokens=1000, output_tokens=500, cache_read_input_tokens=0, cache_creation_input_tokens=0)
        return Stream(SimpleNamespace(model="claude-sonnet-5-5", stop_reason="tool_use", usage=usage, content=responses.pop(0)))

    return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=stream)))


def test_a_correction_keeps_the_rest_reads_the_app_and_can_be_undone(writer, db_session):
    """Seb, 20/11 : « Ce qu'il faut changer » sous le rapport ; le modèle lit
    l'appli (effectifs), ajoute une partie, les montants restent des repères ;
    « Annuler la dernière correction » rend le rapport d'avant."""
    w, seen, _ = writer
    first = w.write(db_session, TRESORIER, 1, SEASON, "", "claude-sonnet-5-5", [])
    corrected = {
        **DRAFT, "points": [], "impossible": None,
        "complements": [{
            "titre": "Effectifs", "paragraphes": ["Nous comptons 163 élèves pour {{produits.706}} de cotisations."],
            "tableau": {"entetes": ["Saison", "Élèves"], "lignes": [["2024-2025", "151"], ["2025-2026", "163"]]},
        }],
    }
    read = []
    w.readings = ([{"name": "resume_ecole", "description": "", "input_schema": {"type": "object", "properties": {}}}],
                  lambda db, member, name, args: read.append((name, args)) or "163 élèves, 12 cours.")
    w._client = scripted_client([
        [SimpleNamespace(type="tool_use", id="t1", name="resume_ecole", input={"saison": None})],
        [SimpleNamespace(type="tool_use", id="t2", name="rendre_rapport", input=corrected)],
    ], seen)
    result = w.correct(db_session, TRESORIER, 1, SEASON, "Ajoute un comparatif du nombre d'élèves.")
    assert read == [("resume_ecole", {"saison": None})]
    # Le modèle a reçu le brouillon à repères, pas les montants finis, puis la lecture.
    calls = [x for x in seen if isinstance(x, dict)]
    assert "{{produits.706}}" in calls[-2]["messages"][0]["content"] and calls[-1]["messages"][-1]["content"][0]["content"] == "163 élèves, 12 cours."
    assert seen[-1][0] == "cost" and "correction" in seen[-1][2]
    assert result["recettes"] == first["recettes"] and result["correction"] == "Ajoute un comparatif du nombre d'élèves."
    assert result["complements"][0]["paragraphes"] == ["Nous comptons 163 élèves pour 2 298,00 € de cotisations."]
    assert "draft" not in result
    content, _, _ = w._build(db_session, TRESORIER, 1, SEASON, "docx")
    doc = Document(__import__("io").BytesIO(content))
    assert "Effectifs" in [p.text for p in doc.paragraphs] and doc.tables[0].rows[2].cells[1].text == "163"
    pdf, _, _ = w._build(db_session, TRESORIER, 1, SEASON, "pdf")
    assert "163 élèves" in "".join(p.get_text() for p in pymupdf.open(stream=pdf, filetype="pdf"))

    # Une donnée introuvable : rien n'est changé, le message le dit.
    w._client = scripted_client([[SimpleNamespace(type="tool_use", id="t3", name="rendre_rapport", input={**corrected, "impossible": "Je ne trouve pas les effectifs de 2019."})]], seen)
    with pytest.raises(ValueError, match="2019"):
        w.correct(db_session, TRESORIER, 1, SEASON, "Compare à 2019.")
    assert w.get(db_session, 1)["id"] == result["id"]

    assert w.undo(db_session, 1)["id"] == first["id"]
    with pytest.raises(LookupError):
        w.undo(db_session, 1)  # la rédaction elle-même ne s'annule pas
