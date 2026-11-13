"""A poll in a conversation, like WhatsApp's (Seb, 13 November 2026;
spec/modules/messagerie-instantanee.md §4.11)."""

import pytest
from conftest import entetes_session

from test_messagerie_actions import _envoyer, _groupe, _setup

SONDAGE = {"question": "Quel jour pour le stage ?", "multiple": False, "options": ["Samedi", " Dimanche ", ""]}


def _options(message):
    return {o["label"]: o for o in message["poll"]["options"]}


def test_sondage_comme_whatsapp(client, db_session):
    from app.main import evenements_client

    ecole, _, prof, eleve, cours = _setup(db_session)
    conv = _groupe(client, ecole, cours)

    # Sent as a message: the question, the answers trimmed, no empty one.
    envoi = _envoyer(client, conv["id"], prof.id, "", poll=SONDAGE)
    assert envoi.status_code == 201
    message = envoi.json()
    assert message["poll"]["question"] == "Quel jour pour le stage ?"
    assert [o["label"] for o in message["poll"]["options"]] == ["Samedi", "Dimanche"]
    samedi, dimanche = (o["id"] for o in message["poll"]["options"])

    # A vote shows live, with the voter's name, in everyone's thread.
    queue = evenements_client.abonner(prof.id)
    try:
        vote = client.put(f"/messages/{message['id']}/vote", json={"compte_id": eleve.id, "options": [samedi]})
        assert vote.status_code == 200
        maj = queue.get_nowait()
        assert maj["type"] == "message_maj"
        assert _options(maj["message"])["Samedi"]["voters"] == ["Léon Perrin"]
        assert _options(maj["message"])["Samedi"]["voter_ids"] == [eleve.id]
    finally:
        evenements_client.desabonner(prof.id, queue)

    # One answer only: a new vote replaces the old one.
    changement = client.put(f"/messages/{message['id']}/vote", json={"compte_id": eleve.id, "options": [dimanche]}).json()
    assert _options(changement)["Samedi"]["voters"] == []
    assert _options(changement)["Dimanche"]["voters"] == ["Léon Perrin"]
    assert changement["poll"]["voters"] == 1
    # ...and two at once are refused.
    deux = client.put(f"/messages/{message['id']}/vote", json={"compte_id": eleve.id, "options": [samedi, dimanche]})
    assert deux.status_code == 400

    # The thread shows the poll too.
    liste = client.get(f"/conversations/{conv['id']}/messages").json()
    assert _options(liste[-1])["Dimanche"]["voter_ids"] == [eleve.id]

    # A poll needs a question and 2 answers.
    sans_question = _envoyer(client, conv["id"], prof.id, "", poll={**SONDAGE, "question": " "})
    assert sans_question.status_code == 422
    une_reponse = _envoyer(client, conv["id"], prof.id, "", poll={**SONDAGE, "options": ["Oui", "oui"]})
    assert une_reponse.status_code == 422

    # A message without a poll has none.
    assert _envoyer(client, conv["id"], prof.id, "Merci").json()["poll"] is None


def test_plusieurs_reponses_et_seulement_les_membres(client, db_session):
    ecole, admin, prof, eleve, cours = _setup(db_session)
    conv = _groupe(client, ecole, cours)
    message = _envoyer(client, conv["id"], prof.id, "", poll={**SONDAGE, "multiple": True}).json()
    ids = [o["id"] for o in message["poll"]["options"]]

    both = client.put(f"/messages/{message['id']}/vote", json={"compte_id": eleve.id, "options": ids}).json()
    assert [o["voters"] for o in both["poll"]["options"]] == [["Léon Perrin"], ["Léon Perrin"]]
    # Removing every answer withdraws the vote.
    aucun = client.put(f"/messages/{message['id']}/vote", json={"compte_id": eleve.id, "options": []}).json()
    assert aucun["poll"]["voters"] == 0

    # Someone outside the conversation does not vote.
    dm = client.post("/dm", params={"ecole_id": ecole.id, "compte_a_id": admin.id, "compte_b_id": prof.id}).json()
    autre = _envoyer(client, dm["id"], admin.id, "", poll=SONDAGE).json()
    refus = client.put(f"/messages/{autre['id']}/vote", json={"compte_id": eleve.id, "options": [autre["poll"]["options"][0]["id"]]})
    assert refus.status_code == 403
    # An answer of another poll is refused.
    croise = client.put(f"/messages/{message['id']}/vote", json={"compte_id": eleve.id, "options": [autre["poll"]["options"][0]["id"]]})
    assert croise.status_code == 400

    # A deleted poll is gone, and nobody votes on it any more.
    client.delete(f"/messages/{message['id']}")
    assert client.put(f"/messages/{message['id']}/vote", json={"compte_id": eleve.id, "options": [ids[0]]}).status_code == 404


@pytest.mark.rbac_reel
def test_on_vote_pour_soi(client, db_session):
    ecole, admin, prof, eleve, cours = _setup(db_session)
    conv = _groupe(client, ecole, cours, headers=entetes_session(admin))
    message = _envoyer(client, conv["id"], prof.id, "", poll=SONDAGE, headers=entetes_session(prof)).json()
    option = message["poll"]["options"][0]["id"]
    assert client.put(
        f"/messages/{message['id']}/vote", json={"compte_id": eleve.id, "options": [option]}, headers=entetes_session(prof)
    ).status_code == 403
    assert client.put(
        f"/messages/{message['id']}/vote", json={"compte_id": eleve.id, "options": [option]}, headers=entetes_session(eleve)
    ).status_code == 200
