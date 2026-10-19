"""Photos and files of the messages (spec/modules/messagerie-instantanee.md
§4.3-4.4, §4.6)."""

import io

import pytest
from conftest import entetes_session
from PIL import Image

from app.main import app, messagerie_receiver
from comptes import Comptes, rbac
from cours import CoursService
from ecoles import Ecoles


@pytest.fixture(autouse=True)
def _stockage_temporaire(tmp_path, monkeypatch):
    monkeypatch.setattr(messagerie_receiver.attachments.storage, "root", tmp_path)
    return tmp_path


def _setup(db_session):
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    comptes = Comptes()
    admin = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia")
    prof = comptes.create(db_session, ecole_id=ecole.id, role="professeur", nom="Blanc", prenom="Ima")
    eleve = comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="Perrin", prenom="Léon")
    cours = CoursService().create(db_session, ecole_id=ecole.id, nom="Eveil")
    CoursService().inscrire_eleve(db_session, cours.id, eleve.id)
    CoursService().ajouter_professeur(db_session, cours.id, prof.id)
    return ecole, admin, prof, eleve, cours


def _groupe(client, ecole, cours, headers=None):
    return client.post(
        "/conversations",
        params={"ecole_id": ecole.id},
        json={"membres": [{"membre_type": "cours", "membre_id": cours.id}]},
        headers=headers,
    ).json()


def _photo(largeur=1600, hauteur=1200):
    tampon = io.BytesIO()
    Image.new("RGB", (largeur, hauteur), (200, 100, 50)).save(tampon, "JPEG")
    return tampon.getvalue()


def _televerser(client, conversation_id, nom, contenu, headers=None, par=None):
    """`par` : who uploads, when sessions are off (they are in most tests)."""
    if par is not None:
        app.dependency_overrides[rbac.compte_appelant] = lambda: par
    return client.post(
        f"/conversations/{conversation_id}/attachments",
        files={"fichier": (nom, contenu)},
        headers=headers,
    )


def test_photo_is_stored_with_a_thumbnail_and_sent_with_the_message(client, db_session, _stockage_temporaire):
    ecole, _, prof, _, cours = _setup(db_session)
    conv = _groupe(client, ecole, cours)

    piece = _televerser(client, conv["id"], "gala.jpg", _photo(), par=prof).json()
    assert piece["kind"] == "photo"
    assert (piece["width"], piece["height"]) == (1600, 1200)

    message = client.post(
        f"/conversations/{conv['id']}/messages",
        json={"expediteur_id": prof.id, "contenu": "", "attachment_ids": [piece["id"]]},
    ).json()
    assert [a["id"] for a in message["attachments"]] == [piece["id"]]

    vignette = client.get(f"/attachments/{piece['id']}/thumbnail")
    assert vignette.status_code == 200
    assert len(vignette.content) < 30_000  # a light thumbnail, not the photo (§4.6)
    assert client.get(f"/attachments/{piece['id']}").content == _photo()
    # Rangé dans le dossier de l'école.
    assert any((_stockage_temporaire / str(ecole.id)).rglob("*"))


def test_other_file_is_kept_untouched(client, db_session):
    ecole, _, prof, _, cours = _setup(db_session)
    conv = _groupe(client, ecole, cours)
    piece = _televerser(client, conv["id"], "planning.pdf", b"%PDF-1.4 test", par=prof).json()
    assert piece["kind"] == "file"
    assert piece["size"] == len(b"%PDF-1.4 test")
    assert client.get(f"/attachments/{piece['id']}/thumbnail").status_code == 404


def test_file_over_25_mb_is_refused(client, db_session, monkeypatch):
    ecole, _, prof, _, cours = _setup(db_session)
    conv = _groupe(client, ecole, cours)
    monkeypatch.setattr(messagerie_receiver.attachments.storage, "max_bytes", 10)
    assert _televerser(client, conv["id"], "gros.bin", b"x" * 11, par=prof).status_code == 413


def test_forward_reuses_the_same_content_and_delete_frees_it_only_when_unused(client, db_session, _stockage_temporaire):
    ecole, admin, prof, eleve, cours = _setup(db_session)
    conv = _groupe(client, ecole, cours)
    dm = client.post(
        "/dm", params={"ecole_id": ecole.id, "compte_a_id": prof.id, "compte_b_id": admin.id}
    ).json()
    piece = _televerser(client, conv["id"], "gala.jpg", _photo(), par=prof).json()
    original = client.post(
        f"/conversations/{conv['id']}/messages",
        json={"expediteur_id": prof.id, "contenu": "Photo", "attachment_ids": [piece["id"]]},
    ).json()
    transfere = client.post(
        f"/conversations/{dm['id']}/messages",
        json={"expediteur_id": prof.id, "contenu": "Photo", "forwarded": True, "attachment_ids": [piece["id"]]},
    ).json()
    copie = transfere["attachments"][0]
    assert copie["id"] != piece["id"]
    fichiers = [f for f in _stockage_temporaire.rglob("*") if f.is_file()]

    client.delete(f"/messages/{original['id']}")
    assert [f for f in _stockage_temporaire.rglob("*") if f.is_file()] == fichiers  # still used by the copy
    client.delete(f"/messages/{transfere['id']}")
    assert [f for f in _stockage_temporaire.rglob("*") if f.is_file()] == []


def test_attachment_of_another_member_cannot_be_reused(client, db_session):
    ecole, admin, prof, eleve, cours = _setup(db_session)
    conv = _groupe(client, ecole, cours)
    piece = _televerser(client, conv["id"], "a.pdf", b"a", par=prof).json()
    reponse = client.post(
        f"/conversations/{conv['id']}/messages",
        json={"expediteur_id": admin.id, "contenu": "x", "attachment_ids": [piece["id"]]},
    )
    # Uploaded by the teacher: the admin cannot send it as theirs.
    assert reponse.status_code == 422


@pytest.mark.rbac_reel
def test_only_members_read_an_attachment(client, db_session):
    ecole, admin, prof, eleve, cours = _setup(db_session)
    conv = _groupe(client, ecole, cours, headers=entetes_session(admin))
    piece = _televerser(client, conv["id"], "a.pdf", b"secret", headers=entetes_session(prof)).json()
    assert client.get(f"/attachments/{piece['id']}", headers=entetes_session(eleve)).status_code == 200
    # The admin created the group but is not in it (only the course is).
    assert client.get(f"/attachments/{piece['id']}", headers=entetes_session(admin)).status_code == 403
    assert _televerser(client, conv["id"], "b.pdf", b"x", headers=entetes_session(admin)).status_code == 403
