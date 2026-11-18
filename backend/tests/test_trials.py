"""Module Essai, étape 1 (spec/modules/essai.md) : page publique, mail,
Admin > Essais, suppression au bout d'un an. Aucun mail réel : l'envoi est
remplacé."""

import io
from datetime import date, datetime, timedelta, timezone

import pytest
from ecoles import Ecoles
from PIL import Image


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 20), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def _jpeg() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (3000, 1500), "gray").save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.fixture()
def ecole(db_session):
    ecole = Ecoles().create(db_session, nom="Alliance Sambo Combat La Ciotat", code_postal="13600")
    ecole.email_contact = "club@exemple.fr"
    db_session.commit()
    return ecole


@pytest.fixture()
def allume(db_session, ecole):
    from app import main
    from registry import activation

    activation.set_enabled(db_session, ecole.id, main.MODULES, "trials", True)
    return ecole


@pytest.fixture()
def mails(monkeypatch):
    from app import main

    envoyes = []

    def envoyer(destinataire, sujet, corps, pieces_jointes, **options):
        envoyes.append({"to": destinataire, "subject": sujet, "text": corps, "attachments": pieces_jointes, **options})

    monkeypatch.setattr(main.core.email_envoi, "envoyer_confirmation", envoyer)
    main.core.trials_receiver.limiter.calls.clear()
    return envoyes


def _inscrire(client, ecole, terms_id, people, signatures, email="sophie.martin@exemple.fr"):
    data = {"email": email, "terms_id": str(terms_id)}
    files = []
    for i, p in enumerate(people):
        for cle, valeur in p.items():
            if cle != "certificate":
                data[f"{cle}_{i}"] = str(valeur).lower() if isinstance(valeur, bool) else str(valeur)
        if p.get("certificate", True):
            files.append((f"certificate_{i}", (f"certif{i}.jpg", _jpeg(), "image/jpeg")))
    for k, nom in enumerate(signatures):
        data[f"signature_name_{k}"] = nom
        files.append((f"signature_{k}", (f"signature{k}.png", _png(), "image/png")))
    return client.post(f"/trials/public/orgs/{ecole.id}/registrations", data=data, files=files)


SOPHIE = {"first_name": "Sophie", "last_name": "Martin", "minor": False, "waiver": True}
LEA = {"first_name": "Léa", "last_name": "Martin", "minor": True, "age": 12, "parent_is_first": True, "waiver": True}


def test_page_publique_eteinte_puis_allumee(client, db_session, ecole):
    from app import main
    from registry import activation

    # Éteint par défaut : la page n'existe pas tant que l'école ne l'allume pas.
    assert client.get(f"/trials/public/orgs/{ecole.id}/page").status_code == 404
    activation.set_enabled(db_session, ecole.id, main.MODULES, "trials", True)
    page = client.get(f"/trials/public/orgs/{ecole.id}/page").json()
    assert page["club"] == "Alliance Sambo Combat La Ciotat"
    assert page["title"] == "S'inscrire à un cours d'essai gratuit"
    assert page["terms_number"] == 1
    assert page["link"].endswith("/essai")
    assert "certificat médical n'est pas gardé" in page["privacy"]


def test_reglages_nouvelle_version_de_la_decharge(client, ecole):
    lu = client.get(f"/ecoles/{ecole.id}/trials/settings").json()
    lu.update(
        rules=["Un seul cours d'essai par personne.", "  "],
        min_age=9,
        schedule=[{"day": "Lundi", "time": "19h – 21h", "course": "Sambo MMA", "place": "La Bédoule"}],
        contacts=[{"name": "Roland", "phone": "06 86 13 84 54"}],
    )
    meme = client.put(f"/ecoles/{ecole.id}/trials/settings", json=lu).json()
    assert meme["terms_number"] == 1 and meme["rules"] == ["Un seul cours d'essai par personne."]
    lu["waiver"] = "Nouvelle décharge pour [élève]."
    nouveau = client.put(f"/ecoles/{ecole.id}/trials/settings", json=lu).json()
    assert nouveau["terms_number"] == 2 and nouveau["terms_id"] != meme["terms_id"]
    lu["min_age"] = 1
    assert client.put(f"/ecoles/{ecole.id}/trials/settings", json=lu).status_code == 422


def test_inscription_famille_mail_et_certificat_jamais_garde(client, db_session, ecole, allume, mails):
    from trials import TrialSignature, TrialStudent

    terms_id = client.get(f"/trials/public/orgs/{ecole.id}/page").json()["terms_id"]
    reponse = _inscrire(client, ecole, terms_id, [SOPHIE, LEA], ["Sophie Martin"])
    assert reponse.status_code == 201, reponse.text
    personnes = reponse.json()["people"]
    assert [(p["first_name"], p["status"]) for p in personnes] == [("Sophie", "created"), ("Léa", "created")]
    assert personnes[0]["qr"].startswith("data:image/png;base64,")

    (mail,) = mails
    assert mail["to"] == "sophie.martin@exemple.fr" and mail["copie"] == "club@exemple.fr"
    assert mail["repondre_a"] == "club@exemple.fr"
    assert mail["subject"] == "Cours d'essai : Sophie Martin"
    assert [nom for nom, _ in mail["attachments"]] == ["certificat-Sophie-Martin.jpg", "certificat-Lea-Martin.jpg"]
    # Photo réduite à 2000 px.
    assert max(Image.open(io.BytesIO(mail["attachments"][0][1])).size) == 2000
    assert [cid for cid, _ in mail["images"]] == ["qr-0", "qr-1", "signature-0"]
    assert "autorisation parentale pour Léa Martin" in mail["text"]

    lea = db_session.query(TrialStudent).filter_by(first_name="Léa").one()
    assert (lea.age, lea.parent_name, lea.certificate_at is not None) == (12, "Sophie Martin", True)
    assert not hasattr(lea, "medical_certificate_file")
    signature = db_session.query(TrialSignature).one()
    assert (signature.signer_name, signature.children) == ("Sophie Martin", ["Léa Martin"])

    # Déjà inscrite : pas recréée, même QR code.
    jeton = lea.token
    encore = _inscrire(client, ecole, terms_id, [SOPHIE], ["Sophie Martin"])
    assert encore.json()["people"][0]["status"] == "existing"
    assert db_session.query(TrialStudent).count() == 2 and lea.token == jeton


def test_inscription_refusee(client, db_session, ecole, allume, mails, monkeypatch):
    from app import main
    from trials import TrialStudent

    terms_id = client.get(f"/trials/public/orgs/{ecole.id}/page").json()["terms_id"]
    sans_signature = _inscrire(client, ecole, terms_id, [SOPHIE, LEA], [])
    assert sans_signature.status_code == 422 and sans_signature.json()["detail"] == "Merci de faire signer Sophie Martin"
    sans_certificat = _inscrire(client, ecole, terms_id, [{**SOPHIE, "certificate": False}], ["Sophie Martin"])
    assert sans_certificat.json()["detail"] == "Merci de joindre le certificat médical de Sophie Martin"
    trop_jeune = _inscrire(client, ecole, terms_id, [SOPHIE, {**LEA, "age": 2}], ["Sophie Martin"])
    assert "à partir de 6 ans" in trop_jeune.json()["detail"]
    ancienne_page = _inscrire(client, ecole, terms_id + 99, [SOPHIE], ["Sophie Martin"])
    assert "rechargez" in ancienne_page.json()["detail"]

    # Le mail ne part pas : rien n'est gardé.
    def panne(*args, **kwargs):
        raise OSError("Brevo ne répond pas")

    monkeypatch.setattr(main.core.email_envoi, "envoyer_confirmation", panne)
    echec = _inscrire(client, ecole, terms_id, [SOPHIE], ["Sophie Martin"])
    assert echec.status_code == 422 and echec.json()["detail"] == "Envoi impossible, réessayez dans un instant"
    assert db_session.query(TrialStudent).count() == 0


def test_limite_de_demandes(client, ecole, allume, mails):
    from app import main

    main.core.trials_receiver.limiter.limit = 2
    try:
        terms_id = client.get(f"/trials/public/orgs/{ecole.id}/page").json()["terms_id"]
        codes = [_inscrire(client, ecole, terms_id, [SOPHIE], ["Sophie Martin"]).status_code for _ in range(3)]
        assert codes == [201, 201, 429]
    finally:
        main.core.trials_receiver.limiter.limit = 10


def test_admin_liste_cours_fiche_suppression(client, db_session, ecole, allume, mails):
    from comptes import Comptes

    terms_id = client.get(f"/trials/public/orgs/{ecole.id}/page").json()["terms_id"]
    _inscrire(client, ecole, terms_id, [SOPHIE, LEA], ["Sophie Martin"])
    # Léa est devenue élève de l'école : « Pas encore adhérents » la cache.
    Comptes().create(db_session, ecole.id, "eleve", "Martin", "Lea")
    liste = client.get(f"/ecoles/{ecole.id}/trials/students").json()
    assert {s["first_name"]: s["member"] for s in liste} == {"Sophie": False, "Léa": True}
    sophie = next(s for s in liste if s["first_name"] == "Sophie")

    base = f"/ecoles/{ecole.id}/trials/students/{sophie['id']}"
    un = client.post(f"{base}/courses").json()
    assert un["course1_date"] == date.today().isoformat() and un["course1_mode"] == "manual"
    assert client.post(f"{base}/courses").json()["detail"] == "Cours déjà noté aujourd'hui"
    hier = (date.today() - timedelta(days=7)).isoformat()
    corrige = client.patch(base, json={"course1_date": hier, "comment": "Revient jeudi"}).json()
    assert (corrige["course1_date"], corrige["comment"]) == (hier, "Revient jeudi")
    assert client.post(f"{base}/courses").json()["course2_date"] == date.today().isoformat()
    client.patch(base, json={"course2_date": (date.today() - timedelta(days=1)).isoformat()})
    plein = client.post(f"{base}/courses")
    assert plein.status_code == 409 and plein.json()["detail"] == "Les 2 cours d'essai sont déjà faits"

    fiche = client.get(base).json()
    assert fiche["family"] == ["Léa Martin"] and fiche["terms_number"] == 1
    assert fiche["signatures"][0]["png"].startswith("data:image/png;base64,")

    assert client.delete(base).status_code == 204
    assert client.get(base).status_code == 404


def test_suppression_au_bout_d_un_an(client, db_session, ecole, allume, mails):
    from app import main
    from trials import TrialSignature, TrialStudent

    terms_id = client.get(f"/trials/public/orgs/{ecole.id}/page").json()["terms_id"]
    _inscrire(client, ecole, terms_id, [SOPHIE, LEA], ["Sophie Martin"])
    vieux = datetime.now(timezone.utc) - timedelta(days=400)
    for row in db_session.query(TrialStudent):
        row.created_at = vieux
    # Léa a fait un cours il y a 6 mois : gardée.
    db_session.query(TrialStudent).filter_by(first_name="Léa").one().course1_date = date.today() - timedelta(days=180)
    db_session.commit()
    assert main.core.trials_client.purge_expired(db_session) == 1
    assert [r.first_name for r in db_session.query(TrialStudent)] == ["Léa"]
    assert db_session.query(TrialSignature).count() == 1
