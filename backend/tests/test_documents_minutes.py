"""Procès-verbal d'assemblée générale (proces-verbal-ag.md, étape 2) : le PV
proposé, chiffres écrits par l'appli, puis les signatures du bureau, le PDF
refait et l'email à l'adresse de contact à chaque signature."""

from datetime import datetime

import pymupdf
import pytest
from test_documents import Docs, _par_nom, ecole, stockage  # noqa: F401 (fixtures)
from test_documents_app import mails  # noqa: F401 (fixture)
from test_documents_assembly import (  # noqa: F401 (fixture)
    PNG,
    ag,
    lien,
    procuration,
    repondre,
)

from documents import assembly, minutes
from ecoles.models import Ecole

pytestmark = pytest.mark.rbac_reel

TITRE = "AGO du 21 novembre 2099"
PV = f"PV de l'{TITRE}"


@pytest.fixture
def apres_ag(monkeypatch):
    """Le lendemain de l'assemblée."""
    monkeypatch.setattr(assembly, "now_local", lambda: datetime(2099, 11, 22, 10, 0))


@pytest.fixture
def tenue(client, ecole, ag, mails, db_session):
    """L'AG a eu lieu : Léon a donné procuration à Ima ; Julia et Ima sont
    pointées présentes. Julia préside, Ima est secrétaire."""
    leon = lien(mails, "leon@exemple.fr")
    ima = next(g["id"] for g in client.get(f"/documents/public/links/{leon}").json()["assembly"]["candidates"] if g["name"] == "Ima Blanc")
    assert procuration(client, leon, ima).status_code == 201
    ecole["admin"].bureau_functions = ["president"]
    ecole["prof"].bureau_functions = ["secretary", "treasurer"]
    db_session.get(Ecole, ecole["id"]).email_contact = "contact@exemple.fr"
    db_session.commit()
    admin = ag["admin"]
    for compte in ("admin", "prof"):
        assert admin.c.put(f"{admin.base}/nodes/{ag['id']}/app/attendance/{ecole[compte].id}", json={"present": True}, headers=admin.h).status_code == 200
    return ag


def textes(f):
    return [assembly.app_content._inline_text(b["content"]) for b in f["content"]["entry"]["blocks"] if b["content"]]


def test_pv_propose(client, ecole, tenue, monkeypatch, db_session):
    admin = tenue["admin"]
    # L'assemblée n'a pas encore eu lieu : rien à produire.
    assert admin.get("/minutes/pending").json() == {"items": []}
    monkeypatch.setattr(assembly, "now_local", lambda: datetime(2099, 11, 22, 10, 0))
    attente = admin.get("/minutes/pending").json()["items"]
    assert [(a["id"], a["title"]) for a in attente] == [(tenue["id"], TITRE)]
    # Le bandeau du dossier de l'AG ; rien ailleurs.
    assert len(admin.get("/minutes/pending", folder_id=tenue["folder"]).json()["items"]) == 1
    assert admin.get("/minutes/pending", folder_id=tenue["folder"] + 999).json()["items"] == []
    # Une autre école ne voit rien.
    voisin = Docs(client, ecole["admin_voisin"].ecole_id, ecole["admin_voisin"])
    assert voisin.get("/minutes/pending").json()["items"] == []

    r = admin.c.post(f"{admin.base}/minutes", json={"convocation_id": tenue["id"]}, headers=admin.h)
    assert r.status_code == 201, r.text
    assert r.json()["name"] == PV and r.json()["folder_id"] == tenue["folder"]
    f = admin.get(f"/nodes/{r.json()['id']}/app").json()
    assert (f["status"], f["family"]) == ("draft", "question")
    t = textes(f)
    assert "L'assemblée générale ordinaire s'est réunie le samedi 21 novembre 2099 à 14 h, À compléter : le lieu." in t
    assert "Présidence de séance : Julia Dho." in t and "Secrétaire de séance : Ima Blanc." in t
    assert "2 membres présents et 1 membre représenté, soit 3 voix sur 4 membres convoqués." in t
    assert "2. Rapport financier et approbation des comptes" in t
    assert t.count("À compléter : ce qui a été dit et le résultat du vote") == 5
    # Les chiffres de l'appli en bleu, le reste à compléter en jaune.
    presence = next(b for b in f["content"]["entry"]["blocks"] if "membres présents" in assembly.app_content._inline_text(b["content"]))
    assert presence["content"][0] == {"type": "text", "text": "2 membres présents", "styles": {"textColor": "blue"}}
    signature = minutes.block_of(f["content"])
    assert signature["props"]["minutesOf"] == tenue["id"]
    # Fait : plus rien n'attend ; pas deux PV pour la même assemblée.
    assert admin.get("/minutes/pending").json()["items"] == []
    r = admin.c.post(f"{admin.base}/minutes", json={"convocation_id": tenue["id"]}, headers=admin.h)
    assert r.status_code == 409 and PV in r.json()["detail"]
    assert voisin.get(f"/nodes/{f['id']}/app/minutes").status_code == 404


def test_texte_bilan_et_pv_de_l_an_dernier(client, ecole, tenue, db_session):
    """Le rapport financier lit le bilan officiel ; le texte de l'an dernier
    est repris sous le même point, chaque nombre surligné « à vérifier »."""
    from documents.app_files import AppFiles

    convocation = db_session.get(assembly.DocNode, tenue["id"])
    contenu = AppFiles.current_version(db_session, convocation).content
    s = {
        "convoked": 10, "present": 4, "represented": 2, "votes": 6, "lost": 1,
        "quorum": {"rule": "half", "needed": 5, "votes": 6, "reached": True},
    }
    an_dernier = {
        "rapport moral": [{"type": "paragraph", "content": [{"type": "text", "text": "Adopté par 12 voix sur 14.", "styles": {}}]}],
    }
    rapport = {"season": "2098-2099", "income": 12450.5, "expense": 11200.0, "result": 1250.5}
    c = minutes.minutes_content("Contretemps", convocation, contenu, s, datetime(2099, 10, 30), [], rapport, an_dernier)
    blocs = c["entry"]["blocks"]
    t = [assembly.app_content._inline_text(b["content"]) for b in blocs]
    assert "Le bilan de la saison 2098-2099 présente 12 450,50 € de recettes et 11 200 € de dépenses, soit un résultat de 1 250,50 €." in t
    assert "Le quorum, fixé à la moitié des membres, soit 5 voix, est atteint : l'assemblée peut valablement délibérer." in t
    assert "1 pouvoir n'a pas été pris en compte : le représentant était absent." in t
    assert "Les membres ont été convoqués par email le 30 octobre 2099 (10 membres convoqués)." in t
    assert "Présidence de séance : À compléter : qui préside." in t
    repris = next(b for b in blocs if "Adopté par" in assembly.app_content._inline_text(b["content"]))
    assert [(r["text"], r["styles"]) for r in repris["content"]] == [
        ("Adopté par ", {}), ("12", {"backgroundColor": "yellow"}), (" voix sur ", {}), ("14", {"backgroundColor": "yellow"}), (".", {}),
    ]
    assert "À compléter : texte repris du procès-verbal de l'an dernier, à adapter" in t
    # Quorum non atteint : écrit tel quel, sans blocage.
    s["quorum"] = {"rule": "half", "needed": 5, "votes": 4, "reached": False}
    t = [assembly.app_content._inline_text(b["content"]) for b in minutes.minutes_content("X", convocation, contenu, s, None, [], None, {})["entry"]["blocks"]]
    assert any("n'est pas atteint" in x for x in t)
    assert not any("bilan" in x for x in t)


def test_signatures_du_bureau(client, ecole, tenue, mails, apres_ag, db_session):
    admin = tenue["admin"]
    pv = admin.c.post(f"{admin.base}/minutes", json={"convocation_id": tenue["id"]}, headers=admin.h).json()["id"]
    signer = lambda ids: admin.c.post(f"{admin.base}/nodes/{pv}/app/minutes/sign", json={"person_ids": ids}, headers=admin.h)  # noqa: E731
    julia, ima = ecole["admin"].id, ecole["prof"].id
    assert signer([julia, ima]).status_code == 409  # pas encore validé
    assert admin.modifier(pv, change_status=True, status="validated").status_code == 200
    etat = admin.get(f"/nodes/{pv}/app/minutes").json()
    assert [(b["name"], b["functions"], b["default"]) for b in etat["board"]] == [
        ("Ima Blanc", "secrétaire, trésorier·e", True), ("Julia Dho", "président·e", True),
    ]
    assert etat["members"] == 4 and etat["signers"] == []

    avant = len(mails.envoyes)
    assert signer([julia, ima]).json() == {"sent": 2}
    a_signer = mails.envoyes[avant:]
    assert {m["to"] for m in a_signer} == {"julia@exemple.fr", "ima@exemple.fr"}
    assert all(m["subject"] == f"À signer : procès-verbal de l'{TITRE}" for m in a_signer)
    jeton_ima = lien(mails, "ima@exemple.fr")
    page = client.get(f"/documents/public/links/{jeton_ima}").json()
    assert page["signer"] and page["accepting"] and page["family"] == "question"
    bloc = minutes.block_of(page["content"])
    assert bloc["props"]["label"] == "Je soussigné(e) Ima Blanc, secrétaire, trésorier·e, certifie ce procès-verbal exact."

    # Ima signe : PDF rangé, email au contact avec le PDF, encore Validé.
    avant = len(mails.envoyes)
    assert client.post(f"/documents/public/links/{jeton_ima}/answers", json={"values": {bloc["id"]: PNG}}).status_code == 201
    contact = mails.envoyes[avant:]
    assert [m["to"] for m in contact] == ["contact@exemple.fr"]
    assert contact[0]["subject"] == f"Ima Blanc a signé le procès-verbal de l'{TITRE}"
    assert "(1 signature sur 2)" in contact[0]["text"]
    nom, pdf = contact[0]["attachments"][0]
    assert nom == f"{PV}.pdf"
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    texte = "".join(p.get_text() for p in doc)
    assert "En attente de signature" in texte and "Signé en ligne le" in texte and "Annexe : liste des présents" in texte
    assert len(doc[0].get_images()) + sum(len(p.get_images()) for p in doc[1:]) == 1
    assert f"{PV}.pdf" in _par_nom(admin.racine(dossier=tenue["folder"]))
    etat = admin.get(f"/nodes/{pv}/app/minutes").json()
    assert (etat["status"], etat["signed"]) == ("validated", 1)
    mien = next(s for s in etat["signers"] if s["name"] == "Julia Dho")
    assert mien["token"] and next(s for s in etat["signers"] if s["name"] == "Ima Blanc")["token"] is None
    # Relancer quelqu'un qui a signé : non.
    assert signer([ima]).status_code == 409

    # Julia signe moi-même : tout le monde a signé, le PV devient Officiel.
    avant = len(mails.envoyes)
    r = client.post(f"/documents/public/links/{mien['token']}/answers", json={"values": {bloc["id"]: PNG}})
    assert r.status_code == 201
    assert "Toutes les signatures sont là" in mails.envoyes[avant]["text"]
    assert admin.get(f"/nodes/{pv}/app").json()["status"] == "official"
    assert client.post(f"/documents/public/links/{mien['token']}/answers", json={"values": {bloc["id"]: PNG}}).status_code == 409
    telecharge = admin.get(f"/nodes/{pv}/app/minutes/pdf")
    assert telecharge.status_code == 200 and "Signé en ligne" in "".join(p.get_text() for p in pymupdf.open(stream=telecharge.content, filetype="pdf"))

    # Envoyé aux membres : à lire, sans signature.
    avant = len(mails.envoyes)
    r = admin.c.post(f"{admin.base}/nodes/{pv}/app/sends", json={"principals": [{"type": "member", "id": str(ecole["eleve"].id)}]}, headers=admin.h)
    assert r.status_code == 201
    assert "Voir en ligne :" in mails.envoyes[avant]["text"]
    page = client.get(f"/documents/public/links/{lien(mails, 'leon@exemple.fr')}").json()
    assert page["family"] == "inform" and not page["accepting"] and minutes.block_of(page["content"]) is None

    # Repassé en Brouillon : les signatures s'effacent.
    assert admin.modifier(pv, change_status=True, status="draft").status_code == 200
    etat = admin.get(f"/nodes/{pv}/app/minutes").json()
    assert etat["signed"] == 0 and len(etat["signers"]) == 2


def test_pv_par_l_assistant(client, ecole, ag, mails, apres_ag, db_session):
    from app import main

    compte = ecole["admin"]
    actions = main.assistant_client.actions
    proposer = lambda nom, args: actions.propose(db_session, compte, ecole["id"], compte.id, nom, args)  # noqa: E731
    faire = lambda carte: actions.execute(db_session, ecole["id"], compte.id, carte["jeton"])  # noqa: E731
    # Personne n'est pointé : la photo d'abord.
    texte, carte = proposer("draft_minutes", {})
    assert carte is None and "mark_attendance" in texte
    _, carte = proposer("mark_attendance", {"file": f"Convocation {TITRE}", "names": ["Julia Dho", "Ima Blanc"]})
    assert faire(carte)[0]["ok"]
    _, carte = proposer("draft_minutes", {})
    assert carte["lignes"][0].startswith(f"Préparer le procès-verbal de l'{TITRE} en brouillon")
    assert "2 présents, 0 représentés" in carte["lignes"][0]
    fait = faire(carte)[0]
    # Le PV proposé s'ouvre au-dessus de l'assistant pour être relu (Seb, 21 octobre).
    assert fait["ok"] and fait["ouvrir"]["name"] == PV and fait["ouvrir"]["kind"] == "app"

    # Valider : le PV passe en Validé, pas en Officiel.
    _, carte = proposer("validate_app_file", {"file": PV})
    assert "prêt à envoyer pour signature" in carte["lignes"][0]
    assert faire(carte)[0]["ok"]
    # Personne au bureau : il faut des noms.
    texte, carte = proposer("send_app_file", {"file": PV})
    assert carte is None and "colonne Bureau" in texte
    _, carte = proposer("send_app_file", {"file": PV, "signers": ["Julia Dho", "Ana Roux"]})
    assert carte["lignes"] == [f"Envoyer pour signature « {PV} » à Julia Dho, Ana Roux"]
    assert faire(carte)[0]["ok"]
    noeud = db_session.scalar(assembly.select(assembly.DocNode).where(assembly.DocNode.name == PV))
    assert [s.name for s in minutes.signers(db_session, noeud)] == ["Ana Roux", "Julia Dho"]
    # Où en sont les signatures : lu avec le fichier.
    lu = main.assistant_client.fichier_appli.lire(db_session, main._membre_de(db_session, compte.id, ecole["id"]), noeud.id)
    assert "0 signature sur 2" in lu and "Ana Roux : pas encore signé" in lu
    # Relancer ceux qui n'ont pas signé.
    _, carte = proposer("send_app_file", {"file": PV})
    assert carte["lignes"] == [f"Relancer pour signature « {PV} » à Ana Roux, Julia Dho"]
