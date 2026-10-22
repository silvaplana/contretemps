"""Signer un document (signature-documents.md).

Étape 1, Préparer : le fichier de signature, le document choisi (PDF tel
quel, Word en blocs), les pages de l'Aperçu, et Valider qui fige le
document : empreinte du PDF à signer au journal de preuves, `reset` en
repassant en Brouillon.

Étape 2, Diffuser et signer : « Faire signer à qui ? », le lien personnel
(lu, consentement, signature, refus, expiré, fermé), le journal avec
l'adresse IP et l'appareil."""

import hashlib
import shutil
import subprocess
from datetime import timedelta

import pymupdf
import pytest
from test_documents import Docs, ecole, stockage  # noqa: F401 (fixtures)
from test_documents_app import mails  # noqa: F401 (fixture)
from test_documents_assembly import PNG

from documents import signing
from documents.app_sends import SIGN_ELSEWHERE
from documents.models import DocSend, DocSignEvent, StoredFile
from ecoles.models import Ecole

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
        "signers": 0,
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
    assert r.status_code == 409 and r.json()["detail"] == SIGN_ELSEWHERE
    r = admin.c.post(
        f"{admin.base}/nodes/{cree['id']}/app/sends",
        json={"principals": [{"type": "member", "id": str(ecole["prof"].id)}]}, headers=admin.h,
    )
    assert r.status_code == 409 and r.json()["detail"] == SIGN_ELSEWHERE
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

    # Valider : figé, en Validé (pas Officiel) ; l'envoi : test_envoi_par_l_assistant.
    _, carte = proposer("validate_app_file", {"file": "Signature : Contrat intervenant"})
    assert "le document est figé (empreinte enregistrée)" in carte["lignes"][0]
    assert faire(carte)[0]["ok"]
    assert fichier_appli(admin, f["id"])["status"] == "validated"
    assert evenements(db_session, f["id"]) == ["validated"]


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


# ----------------------------------------------------------------------
# Étape 2 : Diffuser et signer
# ----------------------------------------------------------------------

NAVIGATEUR = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) Chrome/130", "X-Forwarded-For": "203.0.113.7, 10.0.0.2"}


def jeton(mails, adresse):
    return next(m for m in reversed(mails.envoyes) if m["to"] == adresse)["text"].split("/r/")[1].split()[0]


@pytest.fixture
def a_signer(client, ecole, mails, db_session):
    """« Signature : Bail » en Brouillon, avec paraphe ; Julia (présidente) et
    Ima ont une adresse. Rend (Julia dans Docs, id du fichier)."""
    ecole["admin"].definir_emails("julia@exemple.fr")
    ecole["prof"].definir_emails("ima@exemple.fr")
    ecole["admin"].bureau_functions = ["president"]
    db_session.get(Ecole, ecole["id"]).email_contact = "contact@exemple.fr"
    db_session.commit()
    admin = Docs(client, ecole["id"], ecole["admin"])
    r = admin.fichier("Bail.pdf", contenu=pdf("Article 1", "Article 2"))
    assert r.status_code == 201, r.text
    source = r.json()["id"]
    cree = nouveau(admin, source_id=source)
    f = fichier_appli(admin, cree["id"])
    signing.block_of(f["content"])["props"].update(mode="initials", message="Avant le 30 novembre, merci.")
    assert admin.c.put(f"{admin.base}/nodes/{cree['id']}/app", json={"content": f["content"]}, headers=admin.h).status_code == 200
    return admin, cree["id"]


def envoyer(admin, node_id, principals=(), others=()):
    return admin.c.post(
        f"{admin.base}/nodes/{node_id}/app/signing/send",
        json={"principals": list(principals), "others": list(others)}, headers=admin.h,
    )


def test_faire_signer_a_qui(client, ecole, mails, a_signer, db_session):
    admin, a_signer = a_signer
    julia, ima, leon = (str(ecole[k].id) for k in ("admin", "prof", "eleve"))
    url = f"{admin.base}/nodes/{a_signer}/app/signing"
    # Pas encore validé : rien ne part.
    assert envoyer(admin, a_signer, [{"type": "member", "id": julia}]).status_code == 409
    assert etat(admin, a_signer, "validated").status_code == 200

    vue = admin.get(f"/nodes/{a_signer}/app/signing/signers").json()
    # Présidence, secrétariat et trésorerie toujours proposés, même sans titulaire (Seb, 22 octobre).
    assert vue["board"] == [
        {"function": "Président·e", "person_id": ecole["admin"].id, "name": "Julia Dho"},
        {"function": "Secrétaire", "person_id": None, "name": None},
        {"function": "Trésorier·e", "person_id": None, "name": None},
    ]
    assert vue["signers"] == [] and vue["available"]

    # Le récapitulatif : Léon n'a pas d'adresse, il ne bloque pas les autres.
    corps = {
        "principals": [{"type": "member", "id": i} for i in (julia, ima, leon)],
        "others": [{"name": "Paul Expert", "email": "Paul@Cabinet.fr"}],
    }
    recap = admin.c.post(f"{url}/preview", json=corps, headers=admin.h).json()
    assert recap["count"] == 3 and recap["without_email"] == ["Léon Perrin"]
    assert {r["email"] for r in recap["recipients"]} == {"julia@exemple.fr", "ima@exemple.fr", "paul@cabinet.fr"}
    r = admin.c.post(f"{url}/preview", json={"others": [{"name": "X", "email": "pas-une-adresse"}]}, headers=admin.h)
    assert r.status_code == 422 and "pas valable" in r.json()["detail"]

    avant = len(mails.envoyes)
    r = admin.c.post(f"{url}/send", json=corps, headers={**admin.h, **NAVIGATEUR})
    assert r.status_code == 201 and r.json() == {"sent": 3}
    partis = mails.envoyes[avant:]
    assert {m["to"] for m in partis} == {"julia@exemple.fr", "ima@exemple.fr", "paul@cabinet.fr"}
    m = next(m for m in partis if m["to"] == "paul@cabinet.fr")
    assert m["subject"] == "À signer : Bail"
    assert "Julia Dho, président·e vous demande de signer ce document : « Bail » (2 pages)." in m["text"]
    assert "Avant le 30 novembre, merci." in m["text"] and "Lire et signer :" in m["text"]
    assert "Ce lien vous est personnel, ne le transférez pas. Il expire le" in m["text"]

    vue = admin.get(f"/nodes/{a_signer}/app/signing/signers").json()
    lignes = {s["name"]: s for s in vue["signers"]}
    assert set(lignes) == {"Julia Dho", "Ima Blanc", "Paul Expert"}
    assert lignes["Paul Expert"]["person_id"] is None and lignes["Paul Expert"]["state"] == "sent"
    assert lignes["Julia Dho"]["token"] and lignes["Ima Blanc"]["token"] is None  # « Signer moi-même »
    envoye = db_session.query(DocSignEvent).filter_by(node_id=a_signer, event="sent").all()
    assert len(envoye) == 3 and envoye[0].ip == "203.0.113.7" and "Android" in envoye[0].user_agent

    # Renvoyer à Ima : le même lien, noté « relancé ».
    lien_ima = jeton(mails, "ima@exemple.fr")
    assert envoyer(admin, a_signer, [{"type": "member", "id": ima}]).json() == {"sent": 1}
    assert jeton(mails, "ima@exemple.fr") == lien_ima
    assert evenements(db_session, a_signer)[-1] == "reminded"

    # Le Diffuser habituel reste fermé à ce fichier.
    r = admin.c.post(f"{admin.base}/nodes/{a_signer}/app/sends", json={"principals": [{"type": "member", "id": ima}]}, headers=admin.h)
    assert r.status_code == 409 and r.json()["detail"] == SIGN_ELSEWHERE

    # Une autre école ne voit ni n'envoie rien.
    voisin = Docs(client, ecole["admin_voisin"].ecole_id, ecole["admin_voisin"])
    assert voisin.get(f"/nodes/{a_signer}/app/signing/signers").status_code == 404
    assert envoyer(voisin, a_signer, [{"type": "member", "id": ima}]).status_code == 404


def test_le_signataire(client, ecole, mails, a_signer, db_session):
    admin, a_signer = a_signer
    assert etat(admin, a_signer, "validated").status_code == 200
    envoyer(admin, a_signer, [{"type": "member", "id": str(ecole["prof"].id)}], [{"name": "Paul Expert", "email": "paul@cabinet.fr"}])
    lien = jeton(mails, "ima@exemple.fr")
    base = f"/documents/public/signing/{lien}"

    # Le lien reçu ouvre la page du signataire (pas le formulaire habituel).
    assert client.get(f"/documents/public/links/{lien}").json() == {"signing": True, "name": "Signature : Bail"}
    assert client.post(f"/documents/public/links/{lien}/answers", json={"values": {}}).status_code == 409

    vue = client.get(base, headers=NAVIGATEUR).json()
    assert (vue["state"], vue["person"], vue["sender"], vue["document"], vue["pages"]) == ("open", "Ima Blanc", "Julia Dho", "Bail", 2)
    assert (vue["mode"], vue["mention"], vue["read"], vue["refused"]) == ("initials", "Lu et approuvé", False, None)
    assert vue["consent"] == "Je soussigné(e) Ima Blanc, ai lu le document « Bail » et je le signe."
    page = client.get(f"{base}/pages/2")
    assert page.status_code == 200 and page.content[:4] == b"\x89PNG"
    assert client.get(f"{base}/pages/3").status_code == 404

    # Sans lecture jusqu'en bas, sans la case, sans tracé ou sans initiales : refusé.
    signer = lambda **c: client.post(f"{base}/sign", json=c, headers=NAVIGATEUR)  # noqa: E731
    r = signer(consent=True, signature=PNG, initials=PNG)
    assert r.status_code == 409 and "jusqu'en bas" in r.json()["detail"]
    assert client.post(f"{base}/read", headers=NAVIGATEUR).json() == {"read": True}
    assert client.get(base).json()["read"] is True
    assert signer(consent=False, signature=PNG, initials=PNG).status_code == 422
    assert signer(consent=True, signature="data:image/png;base64,AAAA", initials=PNG).status_code == 422
    assert signer(consent=True, signature=PNG).status_code == 422  # paraphe demandé

    r = signer(consent=True, signature=PNG, initials=PNG)
    assert r.status_code == 201 and r.json()["signed_at"]
    # Le lien se ferme une fois signé.
    assert client.get(base).json()["state"] == "signed"
    r = signer(consent=True, signature=PNG, initials=PNG)
    assert r.status_code == 409 and r.json()["detail"] == "Vous avez déjà signé ce document."
    assert client.post(f"{base}/refuse", json={"reason": "Non"}).status_code == 409

    # Le journal : ouvert, lu, consenti, signé, avec l'adresse IP et l'appareil.
    journal = db_session.query(DocSignEvent).filter_by(node_id=a_signer).order_by(DocSignEvent.id).all()
    envoi_ima = db_session.query(DocSend).filter_by(token=lien).one()
    siens = [e for e in journal if e.send_id == envoi_ima.id]
    # Chaque ouverture du lien est notée (ici, deux).
    assert [e.event for e in siens] == ["sent", "opened", "read", "opened", "consented", "signed"]
    assert siens[-1].ip == "203.0.113.7" and siens[-1].user_agent.startswith("Mozilla/5.0")
    assert siens[-2].detail["text"] == vue["consent"]
    signe = siens[-1].detail
    assert signe["document_sha256"] == journal[0].detail["sha256"] and signe["signature_sha256"] and signe["initials_sha256"]
    vue = admin.get(f"/nodes/{a_signer}/app/signing/signers").json()
    assert vue["signed"] == 1 and {s["name"]: s["state"] for s in vue["signers"]} == {"Ima Blanc": "signed", "Paul Expert": "sent"}

    # Paul refuse, avec un motif : mail à Julia, le lien reste ouvert.
    lien_paul = jeton(mails, "paul@cabinet.fr")
    assert client.post(f"/documents/public/signing/{lien_paul}/refuse", json={"reason": " "}).status_code == 422
    avant = len(mails.envoyes)
    r = client.post(f"/documents/public/signing/{lien_paul}/refuse", json={"reason": "L'article 2 est faux."}, headers=NAVIGATEUR)
    assert r.status_code == 201
    m = mails.envoyes[avant]
    assert m["to"] == "julia@exemple.fr" and m["subject"] == "Paul Expert ne signe pas « Bail »"
    assert "« L'article 2 est faux. »" in m["text"]
    vue_paul = client.get(f"/documents/public/signing/{lien_paul}").json()
    assert vue_paul["state"] == "open" and vue_paul["refused"] == "L'article 2 est faux."
    ligne = next(s for s in admin.get(f"/nodes/{a_signer}/app/signing/signers").json()["signers"] if s["name"] == "Paul Expert")
    assert (ligne["state"], ligne["reason"]) == ("refused", "L'article 2 est faux.")

    # « Relancer les N » : ni ceux qui ont signé, ni ceux qui ont refusé.
    remind = lambda ids=None: admin.c.post(f"{admin.base}/nodes/{a_signer}/app/signing/remind", json={"send_ids": ids}, headers=admin.h)  # noqa: E731
    assert remind().status_code == 409
    assert remind([ligne["id"]]).json() == {"sent": 1}  # une ligne : oui, même après un refus
    assert remind([envoi_ima.id]).status_code == 409

    # Repassé en Brouillon : signatures annulées, liens en attente.
    assert etat(admin, a_signer, "draft").status_code == 200
    reset = db_session.query(DocSignEvent).filter_by(node_id=a_signer, event="reset").one()
    assert reset.detail["signatures"] == 1
    vue = client.get(base).json()
    assert vue["state"] == "draft" and vue["pages"] == 0
    r = client.post(f"{base}/read")
    assert r.status_code == 409 and "en cours de correction" in r.json()["detail"]
    assert client.get(f"{base}/pages/1").status_code == 404
    # Validé de nouveau : il faut relire et signer encore.
    assert etat(admin, a_signer, "validated").status_code == 200
    vue = client.get(base).json()
    assert (vue["state"], vue["read"]) == ("open", False)
    assert admin.get(f"/nodes/{a_signer}/app/signing/signers").json()["signed"] == 0


def test_lien_expire(client, ecole, mails, a_signer, db_session):
    admin, a_signer = a_signer
    assert etat(admin, a_signer, "validated").status_code == 200
    envoyer(admin, a_signer, [{"type": "member", "id": str(ecole["prof"].id)}])
    lien = jeton(mails, "ima@exemple.fr")
    envoi = db_session.query(DocSend).filter_by(token=lien).one()
    envoi.sent_at = envoi.sent_at - timedelta(days=15)
    db_session.commit()
    vue = client.get(f"/documents/public/signing/{lien}").json()
    assert (vue["state"], vue["pages"]) == ("expired", 0)
    r = client.post(f"/documents/public/signing/{lien}/read")
    assert r.status_code == 410 and r.json()["detail"] == "Ce lien a expiré. Demandez à Julia Dho de vous le renvoyer."
    assert "opened" not in evenements(db_session, a_signer)
    # Relancé : 14 jours de plus, même lien.
    remind = admin.c.post(f"{admin.base}/nodes/{a_signer}/app/signing/remind", json={"send_ids": None}, headers=admin.h)
    assert remind.status_code == 201
    assert client.get(f"/documents/public/signing/{lien}").json()["state"] == "open"
    # Un jeton inconnu, ou celui d'un autre fichier : rien.
    assert client.get("/documents/public/signing/inconnu").status_code == 404


def test_envoi_par_l_assistant(client, ecole, mails, a_signer, db_session):
    from app import main

    admin, a_signer = a_signer
    compte = ecole["admin"]
    actions = main.assistant_client.actions
    proposer = lambda nom, args: actions.propose(db_session, compte, ecole["id"], compte.id, nom, args)  # noqa: E731
    faire = lambda carte: actions.execute(db_session, ecole["id"], compte.id, carte["jeton"])  # noqa: E731
    fichier = {"file": "Signature : Bail"}
    texte, carte = proposer("send_app_file", {**fichier, "signers": ["la présidente"]})
    assert carte is None and "pas encore validé" in texte
    assert etat(admin, a_signer, "validated").status_code == 200

    # Sans noms ni envoi : il demande à qui.
    texte, carte = proposer("send_app_file", fichier)
    assert carte is None and "à qui faire signer" in texte
    texte, carte = proposer("send_app_file", {**fichier, "signers": ["Le Trésorier"]})
    assert carte is None and "Le Trésorier" in texte  # personne n'a cette fonction

    _, carte = proposer("send_app_file", {**fichier, "signers": ["la présidente", "Ima Blanc", "élèves"]})
    assert carte["lignes"] == ["Envoyer pour signature « Signature : Bail » à Ima Blanc, Julia Dho ; sans adresse email : Ana Roux, Léon Perrin"]
    assert faire(carte)[0]["ok"]
    vue = admin.get(f"/nodes/{a_signer}/app/signing/signers").json()
    assert {s["name"] for s in vue["signers"]} == {"Julia Dho", "Ima Blanc"}

    # Ensuite, sans noms : relancer ceux qui n'ont pas signé.
    _, carte = proposer("send_app_file", fichier)
    assert carte["lignes"] == ["Relancer pour signature « Signature : Bail » : Ima Blanc, Julia Dho"]
    assert faire(carte)[0]["ok"]
    assert evenements(db_session, a_signer).count("reminded") == 2


# ----------------------------------------------------------------------
# Étape 3 : le journal de preuves et le document signé (§2.5, §3)
# ----------------------------------------------------------------------


def signer_par_lien(client, mails, adresse, initiales=True):
    base = f"/documents/public/signing/{jeton(mails, adresse)}"
    client.get(base, headers=NAVIGATEUR)
    assert client.post(f"{base}/read", headers=NAVIGATEUR).status_code == 200
    corps = {"consent": True, "signature": PNG, "initials": PNG if initiales else None}
    assert client.post(f"{base}/sign", json=corps, headers=NAVIGATEUR).status_code == 201
    return base


def produire(admin, node_id):
    return admin.c.post(f"{admin.base}/nodes/{node_id}/app/signing/produce", headers=admin.h)


def test_document_signe(client, ecole, mails, a_signer, db_session):
    from app import main

    admin, a_signer = a_signer
    compte = ecole["admin"]
    actions = main.assistant_client.actions
    proposer = lambda args: actions.propose(db_session, compte, ecole["id"], compte.id, "produce_signed", args)  # noqa: E731
    assert etat(admin, a_signer, "validated").status_code == 200
    envoyer(admin, a_signer, [{"type": "member", "id": str(ecole["prof"].id)}], [{"name": "Paul Expert", "email": "paul@cabinet.fr"}])
    base_ima = signer_par_lien(client, mails, "ima@exemple.fr")

    # Pas de document signé partiel (décision de Seb), ni par l'écran ni par l'assistant.
    r = produire(admin, a_signer)
    assert r.status_code == 409 and r.json()["detail"] == "Possible quand tout le monde a signé : il manque Paul Expert."
    texte, carte = proposer({"file": "Signature : Bail"})
    assert carte is None and "il manque la signature de Paul Expert" in texte

    # Le journal de preuves, en clair, pour Voir les résultats.
    vue = admin.get(f"/nodes/{a_signer}/app/signing/signers").json()
    journal = vue["journal"]
    assert journal[0]["event"] == "validated" and journal[0]["text"] == "Document validé et figé par Julia Dho, empreinte enregistrée"
    signe = next(e for e in journal if e["event"] == "signed")
    assert (signe["text"], signe["ip"], signe["device"]) == ("Signature de Ima Blanc enregistrée", "203.0.113.7", "Chrome sur Android")
    assert "Lien personnel envoyé à Paul Expert (paul@cabinet.fr)" in [e["text"] for e in journal]
    assert vue["produced"] is None

    signer_par_lien(client, mails, "paul@cabinet.fr")
    _, carte = proposer({"file": "Signature : Bail"})
    assert carte["lignes"] == [(
        "Produire « Bail_Signé_IB_PE.pdf » et ses preuves à côté de l'original, les envoyer par email "
        "aux 2 signataires et passer « Signature : Bail » en Officiel"
    )]
    avant = len(mails.envoyes)
    r = produire(admin, a_signer)
    assert r.status_code == 201, r.text
    fait = r.json()
    # Seb, 22 octobre : les initiales de qui a signé dans le nom ; les preuves à part.
    assert (fait["name"], fait["proof_name"]) == ("Bail_Signé_IB_PE.pdf", "Bail_Preuves de signature.pdf")

    # Rangés à côté de l'original ; le fichier de signature passe Officiel.
    racine = {x["name"]: x["id"] for x in elements(admin.racine().json())}
    assert racine["Bail_Signé_IB_PE.pdf"] == fait["id"] and racine["Bail_Preuves de signature.pdf"] == fait["proof_id"]
    assert "Bail.pdf" in racine
    assert fichier_appli(admin, a_signer)["status"] == "official"
    data = admin.get(f"/nodes/{fait['id']}/content").content
    assert hashlib.sha256(data).hexdigest() == fait["sha256"]
    produit = db_session.query(DocSignEvent).filter_by(node_id=a_signer, event="produced").one()
    assert produit.detail["sha256"] == fait["sha256"] and produit.detail["file_id"] == fait["id"]

    # Le PDF : les 2 pages du document, avec les paraphes ; les signatures collées à la fin
    # du texte (il reste de la place) ; rien d'autre.
    doc = pymupdf.open(stream=data, filetype="pdf")
    assert doc.page_count == 2 and "Article 1" in doc[0].get_text() and "Article 2" in doc[1].get_text()
    assert len(doc[0].get_image_info()) == 2 and len(doc[1].get_image_info()) == 4  # paraphes ; paraphes et signatures
    signatures = doc[1].get_text()
    # Sans titre ; la fonction au-dessus du nom (professeur ici), rien pour quelqu'un d'autre.
    assert "Article 2\nProfesseur\nIma Blanc\nLu et approuvé, le " in signatures and "Signatures" not in signatures
    assert "\nPaul Expert\nLu et approuvé, le " in signatures
    assert "Lu et approuvé, le " in signatures and " h " not in signatures and "paul@cabinet.fr" not in signatures and "Certificat" not in signatures
    preuves = admin.get(f"/nodes/{fait['proof_id']}/content").content
    certificat = "".join(p.get_text() for p in pymupdf.open(stream=preuves, filetype="pdf"))
    fige = pdf_fige(db_session, a_signer)
    for attendu in ("Certificat de preuves", "Bail (2 pages)", hashlib.sha256(fige).hexdigest(), "Bail_Signé_IB_PE.pdf",
                    fait["sha256"], "203.0.113.7",
                    "Chrome sur Android", "Signature de Paul Expert enregistrée", "article 1367 du Code civil"):
        assert attendu in certificat.replace("\n", " ").replace("\ufb01", "fi"), (attendu, certificat[:900])

    # Les mails : chaque signataire, l'expéditrice et l'adresse de l'école, les deux PDF joints.
    partis = mails.envoyes[avant:]
    assert sorted(m["to"] for m in partis) == ["contact@exemple.fr", "ima@exemple.fr", "julia@exemple.fr", "paul@cabinet.fr"]
    assert all(m["subject"] == "Signé : Bail" and m["attachments"] == [("Bail_Signé_IB_PE.pdf", data), ("Bail_Preuves de signature.pdf", preuves)] for m in partis)

    # Le signataire voit toujours « signé » ; le suivi montre le document produit.
    assert client.get(base_ima).json()["state"] == "signed"
    vue = admin.get(f"/nodes/{a_signer}/app/signing/signers").json()
    assert vue["produced"]["id"] == fait["id"] and vue["journal"][-1]["event"] == "produced"
    assert vue["source"] == {"id": racine["Bail.pdf"], "name": "Bail.pdf"}
    assert "Document signé produit : « Bail_Signé_IB_PE.pdf »" in signing.status_text(main.documents_client, db_session, signing_node(db_session, a_signer))

    # Le refaire : une nouvelle version du même PDF.
    r = produire(admin, a_signer)
    assert r.status_code == 201 and r.json()["id"] == fait["id"]

    # Le PDF figé abîmé dans le stockage : refus, rien n'est produit.
    chemin = main.documents_client.storage.path(ecole["id"], hashlib.sha256(fige).hexdigest())
    chemin.write_bytes(fige + b"%")
    r = produire(admin, a_signer)
    assert r.status_code == 409 and "a changé depuis la validation" in r.json()["detail"]
    chemin.write_bytes(fige)

    # Seb, 22 octobre : ensuite, l'original et le fichier de signature peuvent
    # partir à la corbeille (le document signé et les preuves restent).
    assert admin.supprimer(racine["Bail.pdf"]).status_code == 204
    assert admin.get(f"/nodes/{a_signer}/app/signing/signers").json()["source"] is None
    assert admin.supprimer(a_signer).status_code == 204


def elements(vue):
    return vue["items"] if isinstance(vue, dict) else vue


def signing_node(db_session, node_id):
    from documents.models import DocNode

    return db_session.get(DocNode, node_id)


def test_initiales():
    assert signing.initials("Marie-Laure Pesenti") == "MLP" and signing.initials("jean de la Tour") == "JDLT"
    fige = DocSignEvent(detail={"source_name": "PV AGO.docx"})
    gens = [DocSend(name=f"Ana B{i}") for i in range(10)]
    assert signing._signed_name(fige, gens[:2]) == "PV AGO_Signé_AB_AB.pdf"
    assert signing._signed_name(fige, gens) == "PV AGO_Signé_" + "_".join(["AB"] * 8) + "_et_2.pdf"


def test_appareil_en_clair():
    assert signing.device("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit Version/17.0 Mobile Safari/604.1") == "Safari sur iPhone"
    assert signing.device("Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0 Safari/537.36 Edg/130.0") == "Edge sur Windows"
    assert signing.device("Mozilla/5.0 (Linux; Android 14; SM-S911B) SamsungBrowser/25.0 Chrome/121 Mobile Safari/537.36") == "Samsung Internet sur Android"
    assert signing.device(None) == ""


@pytest.mark.skipif(shutil.which("soffice") is None, reason="LibreOffice absent")
def test_document_signe_word(client, ecole, mails, db_session, tmp_path):
    """Un Word : les signatures à la suite du texte, sur sa dernière page ;
    dans la case, la fonction, puis le nom, puis la signature."""
    ecole["admin"].definir_emails("julia@exemple.fr")
    ecole["admin"].bureau_functions = ["president"]
    db_session.commit()
    admin = Docs(client, ecole["id"], ecole["admin"])
    (tmp_path / "pv.html").write_text(HTML_WORD, encoding="utf-8")
    subprocess.run(
        ["soffice", "--headless", f"-env:UserInstallation=file://{tmp_path / 'profil'}",
         "--convert-to", "docx:MS Word 2007 XML", "--outdir", str(tmp_path), str(tmp_path / "pv.html")],
        capture_output=True, timeout=120, check=True,
    )
    source = admin.fichier("PV.docx", contenu=(tmp_path / "pv.docx").read_bytes()).json()["id"]
    cree = nouveau(admin, source_id=source)["id"]
    assert etat(admin, cree, "validated").status_code == 200
    pages = pymupdf.open(stream=pdf_fige(db_session, cree), filetype="pdf").page_count
    envoyer(admin, cree, [{"type": "member", "id": str(ecole["admin"].id)}])
    signer_par_lien(client, mails, "julia@exemple.fr", initiales=False)
    r = produire(admin, cree)
    assert r.status_code == 201, r.text
    doc = pymupdf.open(stream=admin.get(f"/nodes/{r.json()['id']}/content").content, filetype="pdf")
    derniere = doc[pages - 1].get_text()
    assert "Clôture\nFin. Signé.\nPrésident·e\nJulia Dho\nLu et approuvé, le " in derniere and "Signé en ligne" not in derniere
    assert doc.page_count == pages
    assert r.json()["name"] == "PV_Signé_JD.pdf"
