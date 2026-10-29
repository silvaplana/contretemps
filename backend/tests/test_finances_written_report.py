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
