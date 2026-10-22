"""Signer un document (signature-documents.md), étape 1 : Préparer. Le
fichier de signature, le document choisi (PDF tel quel, Word en blocs),
les pages de l'Aperçu, et Valider qui fige le document : empreinte du PDF à
signer au journal de preuves, `reset` en repassant en Brouillon."""

import hashlib
import shutil
import subprocess

import pymupdf
import pytest
from test_documents import Docs, ecole, stockage  # noqa: F401 (fixtures)
from test_documents_app import mails  # noqa: F401 (fixture)

from documents import signing
from documents.app_sends import SIGN_LATER
from documents.models import DocSignEvent, StoredFile

pytestmark = pytest.mark.rbac_reel


def pdf(*pages: str) -> bytes:
    doc = pymupdf.open()
    for texte in pages:
        doc.new_page().insert_text((72, 72), texte)
    return doc.tobytes()


def texte_pdf(data: bytes) -> str:
    return "".join(p.get_text() for p in pymupdf.open(stream=data, filetype="pdf"))


@pytest.fixture
def admin(client, ecole):
    return Docs(client, ecole["id"], ecole["admin"])


def nouveau(admin, **corps):
    r = admin.c.post(f"{admin.base}/signings", json={"space": "private", **corps}, headers=admin.h)
    assert r.status_code == 201, r.text
    return r.json()


def fichier_appli(admin, node_id):
    return admin.get(f"/nodes/{node_id}/app").json()


def etat(admin, node_id, status):
    return admin.modifier(node_id, status=status, change_status=True)


def pdf_fige(db_session, node_id) -> bytes:
    """Le PDF à signer rangé à Valider (dernier événement `validated`)."""
    from app import main

    e = db_session.query(DocSignEvent).filter_by(node_id=node_id, event="validated").order_by(DocSignEvent.id.desc()).first()
    stocke = db_session.get(StoredFile, e.detail["stored_file_id"])
    return main.documents_client.storage.path(stocke.org_id, stocke.sha256).read_bytes()


def evenements(db_session, node_id):
    return [e.event for e in db_session.query(DocSignEvent).filter_by(node_id=node_id).order_by(DocSignEvent.id)]


def test_faire_signer_un_pdf(client, ecole, admin, db_session):
    dossier = admin.dossier("Réunions").json()["id"]
    original = pdf("Page un du PV", "Page deux du PV")
    source = admin.fichier("PV AGO 2026.pdf", parent=dossier, contenu=original).json()["id"]

    # « Faire signer… » sur le PDF : le fichier se crée à côté.
    cree = nouveau(admin, source_id=source)
    assert (cree["name"], cree["folder_id"], cree["family"]) == ("Signature : PV AGO 2026", dossier, "question")
    f = fichier_appli(admin, cree["id"])
    assert (f["status"], f["family"]) == ("draft", "question")
    bloc = signing.block_of(f["content"])
    assert bloc["props"] == {"source": source, "mode": "end", "mention": "Lu et approuvé", "message": ""}
    assert len(f["content"]["entry"]["blocks"]) == 1

    vue = admin.get(f"/nodes/{cree['id']}/app/signing").json()
    assert vue == {
        "source": {"id": source, "name": "PV AGO 2026.pdf", "kind": "pdf"}, "missing": False, "frozen": None, "pages": 2,
    }
    image = admin.get(f"/nodes/{cree['id']}/app/signing/pages/2")
    assert image.status_code == 200 and image.headers["content-type"] == "image/png" and image.content[:4] == b"\x89PNG"
    assert admin.get(f"/nodes/{cree['id']}/app/signing/pages/3").status_code == 404

    # Les réglages se changent comme tout fichier de l'appli.
    bloc["props"].update(mode="initials", message="Merci de signer avant le 30 novembre.")
    assert admin.c.put(f"{admin.base}/nodes/{cree['id']}/app", json={"content": f["content"]}, headers=admin.h).status_code == 200
    bloc["props"]["mode"] = "partout"
    r = admin.c.put(f"{admin.base}/nodes/{cree['id']}/app", json={"content": f["content"]}, headers=admin.h)
    assert r.status_code == 422 and "Où signer" in r.json()["detail"]

    # Valider fige le document : l'empreinte du PDF à signer au journal.
    assert etat(admin, cree["id"], "validated").status_code == 200
    vue = admin.get(f"/nodes/{cree['id']}/app/signing").json()
    assert vue["frozen"]["sha256"] == hashlib.sha256(original).hexdigest() and vue["frozen"]["pages"] == 2
    e = db_session.query(DocSignEvent).filter_by(node_id=cree["id"]).one()
    assert (e.event, e.org_id, e.detail["source_id"], e.detail["by"]) == ("validated", ecole["id"], source, ecole["admin"].id)

    # Le PDF déposé change ensuite : l'Aperçu montre toujours le PDF figé.
    r = admin.c.post(
        f"{admin.base}/nodes/{source}/versions", files={"file": ("PV AGO 2026.pdf", pdf("Autre texte"))}, headers=admin.h,
    )
    assert r.status_code in (200, 201), r.text
    assert admin.get(f"/nodes/{cree['id']}/app/signing").json()["pages"] == 2
    # On ne change pas de document une fois validé.
    r = admin.c.put(f"{admin.base}/nodes/{cree['id']}/app/signing/document", json={"source_id": source}, headers=admin.h)
    assert r.status_code == 409

    # Repasser en Brouillon : `reset` au journal, plus rien de figé ; valider
    # de nouveau fige la nouvelle version.
    assert etat(admin, cree["id"], "draft").status_code == 200
    assert admin.get(f"/nodes/{cree['id']}/app/signing").json()["frozen"] is None
    assert etat(admin, cree["id"], "validated").status_code == 200
    assert evenements(db_session, cree["id"]) == ["validated", "reset", "validated"]
    assert "Autre texte" in texte_pdf(pdf_fige(db_session, cree["id"]))
    assert admin.get(f"/nodes/{cree['id']}/app/signing").json()["frozen"]["pages"] == 1

    # Une autre école ne voit rien.
    voisin = Docs(client, ecole["admin_voisin"].ecole_id, ecole["admin_voisin"])
    assert voisin.get(f"/nodes/{cree['id']}/app/signing").status_code == 404
    assert voisin.get(f"/nodes/{cree['id']}/app/signing/pages/1").status_code == 404


def test_tuile_puis_document(client, ecole, admin, db_session):
    cree = nouveau(admin)
    assert cree["name"] == "Faire signer un document"
    # Sans document, Valider explique quoi faire.
    r = etat(admin, cree["id"], "validated")
    assert r.status_code == 409 and "Choisissez d'abord le document" in r.json()["detail"]
    assert fichier_appli(admin, cree["id"])["status"] == "draft" and evenements(db_session, cree["id"]) == []
    assert admin.get(f"/nodes/{cree['id']}/app/signing").json()["pages"] == 0

    # Ni un texte, ni une image : un PDF ou un Word.
    texte = admin.fichier("notes.txt").json()["id"]
    r = admin.c.put(f"{admin.base}/nodes/{cree['id']}/app/signing/document", json={"source_id": texte}, headers=admin.h)
    assert r.status_code == 422 and "PDF ou un Word" in r.json()["detail"]
    source = admin.fichier("Règlement intérieur.pdf", contenu=pdf("Article 1")).json()["id"]
    r = admin.c.put(f"{admin.base}/nodes/{cree['id']}/app/signing/document", json={"source_id": source}, headers=admin.h)
    assert r.status_code == 200 and r.json() == {"kind": "pdf", "name": "Règlement intérieur.pdf"}
    assert fichier_appli(admin, cree["id"])["name"] == "Signature : Règlement intérieur"

    # Le PDF disparaît : on le redemande.
    assert admin.supprimer(source).status_code == 204
    vue = admin.get(f"/nodes/{cree['id']}/app/signing").json()
    assert vue["source"] is None and vue["missing"] is True
    assert etat(admin, cree["id"], "validated").status_code == 409

    # Le PDF d'une autre école n'est pas un document possible.
    voisin = Docs(client, ecole["admin_voisin"].ecole_id, ecole["admin_voisin"])
    ailleurs = voisin.fichier("Secret.pdf", contenu=pdf("x")).json()["id"]
    r = admin.c.put(f"{admin.base}/nodes/{cree['id']}/app/signing/document", json={"source_id": ailleurs}, headers=admin.h)
    assert r.status_code == 404


def test_pas_de_diffuser_habituel(client, ecole, admin, mails):
    source = admin.fichier("Contrat.pdf", contenu=pdf("Contrat")).json()["id"]
    cree = nouveau(admin, source_id=source)
    assert etat(admin, cree["id"], "validated").status_code == 200
    r = admin.c.post(f"{admin.base}/nodes/{cree['id']}/app/sends/trial", headers=admin.h)
    assert r.status_code == 409 and r.json()["detail"] == SIGN_LATER
    r = admin.c.post(
        f"{admin.base}/nodes/{cree['id']}/app/sends",
        json={"principals": [{"type": "member", "id": str(ecole["prof"].id)}]}, headers=admin.h,
    )
    assert r.status_code == 409 and r.json()["detail"] == SIGN_LATER
    # Personne ne « répond » au bloc par un essai : on signe par son lien.
    bloc = signing.block_of(fichier_appli(admin, cree["id"])["content"])
    r = admin.c.post(f"{admin.base}/nodes/{cree['id']}/app/try", json={"values": {bloc["id"]: "x"}}, headers=admin.h)
    assert r.status_code == 422


HTML_WORD = """<html><head><title>x</title><style>p { color: red }</style></head><body>
<h1 class="western">Procès-verbal</h1>
<p class="western">Bonjour <b>gras</b> et <i>it</i>.</p>
<ul><li><p>un</p></li><li><p>deux</p></li></ul>
<ol><li><p>premier</p></li></ol>
<table><tr><td><p>Pour</p></td><td><p> 41</p></td></tr><tr><td><p>Contre</p></td><td><p></p></td></tr></table>
<h4>Clôture</h4><p>Fin.<br/>Signé.</p>
</body></html>"""


def test_word_en_blocs():
    blocs = signing.html_to_blocks(HTML_WORD)
    vu = [(b["type"], b["props"], [(r["text"], r["styles"]) for r in b["content"]]) for b in blocs]
    assert vu == [
        ("heading", {"level": 1}, [("Procès-verbal", {})]),
        ("paragraph", {}, [("Bonjour ", {}), ("gras", {"bold": True}), (" et ", {}), ("it", {"italic": True}), (".", {})]),
        ("bulletListItem", {}, [("un", {})]),
        ("bulletListItem", {}, [("deux", {})]),
        ("numberedListItem", {}, [("premier", {})]),
        ("paragraph", {}, [("Pour · 41", {})]),
        ("paragraph", {}, [("Contre", {})]),
        ("heading", {"level": 3}, [("Clôture", {})]),
        ("paragraph", {}, [("Fin. Signé.", {})]),
    ]
    assert len({b["id"] for b in blocs}) == len(blocs)


@pytest.mark.skipif(shutil.which("soffice") is None, reason="LibreOffice absent")
def test_faire_signer_un_word(client, ecole, admin, db_session, tmp_path):
    (tmp_path / "pv.html").write_text(HTML_WORD, encoding="utf-8")
    subprocess.run(
        ["soffice", "--headless", f"-env:UserInstallation=file://{tmp_path / 'profil'}",
         "--convert-to", "docx:MS Word 2007 XML", "--outdir", str(tmp_path), str(tmp_path / "pv.html")],
        capture_output=True, timeout=120, check=True,
    )
    source = admin.fichier("PV.docx", contenu=(tmp_path / "pv.docx").read_bytes()).json()["id"]
    cree = nouveau(admin, source_id=source)
    f = fichier_appli(admin, cree["id"])
    blocs = f["content"]["entry"]["blocks"]
    assert blocs[0]["type"] == "heading" and blocs[-1]["type"] == "signDocument"
    assert admin.get(f"/nodes/{cree['id']}/app/signing").json()["source"]["kind"] == "word"
    # Un Word en Brouillon : pas de pages, son texte se corrige dans l'Aperçu.
    assert admin.get(f"/nodes/{cree['id']}/app/signing").json()["pages"] == 0
    blocs[0]["content"] = [{"type": "text", "text": "Procès-verbal corrigé", "styles": {}}]
    assert admin.c.put(f"{admin.base}/nodes/{cree['id']}/app", json={"content": f["content"]}, headers=admin.h).status_code == 200

    # Valider : le texte corrigé, mis en page, est ce qui est figé.
    assert etat(admin, cree["id"], "validated").status_code == 200
    fige = pdf_fige(db_session, cree["id"])
    assert "Procès-verbal corrigé" in texte_pdf(fige) and "Pour · 41" in texte_pdf(fige)
    vue = admin.get(f"/nodes/{cree['id']}/app/signing").json()
    assert vue["frozen"]["sha256"] == hashlib.sha256(fige).hexdigest() and vue["pages"] >= 1
    assert admin.get(f"/nodes/{cree['id']}/app/signing/pages/1").status_code == 200


def test_par_l_assistant(client, ecole, admin, db_session):
    from app import main

    compte = ecole["admin"]
    actions = main.assistant_client.actions
    proposer = lambda nom, args: actions.propose(db_session, compte, ecole["id"], compte.id, nom, args)  # noqa: E731
    faire = lambda carte: actions.execute(db_session, ecole["id"], compte.id, carte["jeton"])  # noqa: E731
    texte, carte = proposer("prepare_signature", {"document": "Inconnu.pdf"})
    assert carte is None and "introuvable" in texte
    admin.fichier("Contrat intervenant.pdf", contenu=pdf("Contrat"))
    _, carte = proposer("prepare_signature", {"document": "Contrat intervenant.pdf", "mode": "initials", "message": "Avant vendredi"})
    assert carte["lignes"] == [(
        "Préparer « Signature : Contrat intervenant » à côté de « Contrat intervenant.pdf » "
        "(signature à la fin et paraphe en bas de chaque page), en brouillon, à relire avant de valider"
    )]
    fait = faire(carte)[0]
    assert fait["ok"] and fait["ouvrir"]["name"] == "Signature : Contrat intervenant"
    f = fichier_appli(admin, fait["ouvrir"]["id"])
    assert signing.props(signing.block_of(f["content"])) == {
        "source": signing.props(signing.block_of(f["content"]))["source"], "mode": "initials",
        "mention": "Lu et approuvé", "message": "Avant vendredi",
    }

    # Valider : figé, en Validé (pas Officiel) ; l'envoi arrive à l'étape 2.
    _, carte = proposer("validate_app_file", {"file": "Signature : Contrat intervenant"})
    assert "le document est figé (empreinte enregistrée)" in carte["lignes"][0]
    assert faire(carte)[0]["ok"]
    assert fichier_appli(admin, f["id"])["status"] == "validated"
    assert evenements(db_session, f["id"]) == ["validated"]
    texte, carte = proposer("send_app_file", {"file": "Signature : Contrat intervenant"})
    assert carte is None and "arrive bientôt" in texte


def test_deuxieme_tuile_renommee(client, ecole, admin, db_session):
    # Deux tuiles dans le même dossier : la seconde s'appelle « … (2) » et
    # prend tout de même le nom du document déposé.
    nouveau(admin)
    second = nouveau(admin)
    assert second["name"] == "Faire signer un document (2)"
    source = admin.fichier("Bail.pdf", contenu=pdf("Article 1")).json()["id"]
    r = admin.c.put(f"{admin.base}/nodes/{second['id']}/app/signing/document", json={"source_id": source}, headers=admin.h)
    assert r.status_code == 200
    assert fichier_appli(admin, second["id"])["name"] == "Signature : Bail"
