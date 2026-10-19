"""Actions on a message: edit, delete, forward, reply
(spec/modules/messagerie-instantanee.md §4.2)."""

import datetime as dt

import pytest
from comptes import Comptes
from conftest import entetes_session
from cours import CoursService
from ecoles import Ecoles

from messagerie.models import Message


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


def _envoyer(client, conversation_id, expediteur_id, contenu="Bonjour", headers=None, **extra):
    return client.post(
        f"/conversations/{conversation_id}/messages",
        json={"expediteur_id": expediteur_id, "contenu": contenu, **extra},
        headers=headers,
    )


def test_edit_changes_text_and_marks_it_edited(client, db_session):
    ecole, _, prof, _, cours = _setup(db_session)
    conv = _groupe(client, ecole, cours)
    message = _envoyer(client, conv["id"], prof.id, "Bonjuor").json()
    assert message["edited_at"] is None

    reponse = client.put(f"/messages/{message['id']}", json={"contenu": "Bonjour"})
    assert reponse.status_code == 200
    assert reponse.json()["contenu"] == "Bonjour"
    assert reponse.json()["edited_at"] is not None


def test_edit_refused_after_15_minutes_even_if_unread(client, db_session):
    ecole, _, prof, _, cours = _setup(db_session)
    conv = _groupe(client, ecole, cours)
    message_id = _envoyer(client, conv["id"], prof.id).json()["id"]
    message = db_session.get(Message, message_id)
    message.created_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=16)
    db_session.commit()

    reponse = client.put(f"/messages/{message_id}", json={"contenu": "Trop tard"})
    assert reponse.status_code == 409


def test_delete_keeps_the_message_but_erases_its_text(client, db_session):
    ecole, _, prof, _, cours = _setup(db_session)
    conv = _groupe(client, ecole, cours)
    message_id = _envoyer(client, conv["id"], prof.id, "Secret").json()["id"]

    reponse = client.delete(f"/messages/{message_id}")
    assert reponse.status_code == 200
    assert reponse.json()["contenu"] == ""
    assert reponse.json()["deleted_at"] is not None

    messages = client.get(f"/conversations/{conv['id']}/messages").json()
    assert [m["id"] for m in messages] == [message_id]  # still in place
    # A deleted message can no longer be edited.
    assert client.put(f"/messages/{message_id}", json={"contenu": "x"}).status_code == 409


def test_edit_and_delete_are_published_live_to_members(client, db_session):
    from app.main import evenements_client

    ecole, _, prof, eleve, cours = _setup(db_session)
    conv = _groupe(client, ecole, cours)
    message_id = _envoyer(client, conv["id"], prof.id).json()["id"]

    queue = evenements_client.abonner(eleve.id)
    try:
        client.put(f"/messages/{message_id}", json={"contenu": "Bonsoir"})
        client.delete(f"/messages/{message_id}")
        edit = queue.get_nowait()
        assert edit["type"] == "message_maj"
        assert edit["message"]["contenu"] == "Bonsoir"
        suppression = queue.get_nowait()
        assert suppression["type"] == "message_maj"
        assert suppression["message"]["deleted_at"] is not None
    finally:
        evenements_client.desabonner(eleve.id, queue)


def test_reply_points_to_a_message_of_the_same_conversation(client, db_session):
    ecole, admin, prof, eleve, cours = _setup(db_session)
    conv = _groupe(client, ecole, cours)
    original = _envoyer(client, conv["id"], prof.id, "Cours annulé demain").json()

    reponse = _envoyer(client, conv["id"], eleve.id, "D'accord", reply_to_id=original["id"])
    assert reponse.status_code == 201
    assert reponse.json()["reply_to_id"] == original["id"]

    autre = client.post(
        "/dm", params={"ecole_id": ecole.id, "compte_a_id": admin.id, "compte_b_id": eleve.id}
    ).json()
    refus = _envoyer(client, autre["id"], eleve.id, "x", reply_to_id=original["id"])
    assert refus.status_code == 422


def test_forwarded_flag_is_kept(client, db_session):
    ecole, _, prof, _, cours = _setup(db_session)
    conv = _groupe(client, ecole, cours)
    message = _envoyer(client, conv["id"], prof.id, "À lire", forwarded=True).json()
    assert message["forwarded"] is True


@pytest.mark.rbac_reel
def test_only_the_author_edits_and_admin_deletes_in_groups(client, db_session):
    ecole, admin, prof, eleve, cours = _setup(db_session)
    conv = _groupe(client, ecole, cours, headers=entetes_session(admin))
    message_id = _envoyer(client, conv["id"], prof.id, headers=entetes_session(prof)).json()["id"]

    # Someone else may not edit nor delete it...
    assert client.put(
        f"/messages/{message_id}", json={"contenu": "x"}, headers=entetes_session(eleve)
    ).status_code == 403
    assert client.delete(f"/messages/{message_id}", headers=entetes_session(eleve)).status_code == 403
    # ...except an admin deleting it, in a group (moderation).
    assert client.put(
        f"/messages/{message_id}", json={"contenu": "x"}, headers=entetes_session(admin)
    ).status_code == 403
    assert client.delete(f"/messages/{message_id}", headers=entetes_session(admin)).status_code == 200
