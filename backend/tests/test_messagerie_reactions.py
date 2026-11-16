"""Emoji reactions on a message, like WhatsApp (Seb, 16 November 2026;
spec/modules/messagerie-instantanee.md §4.12)."""

from test_messagerie_actions import _envoyer, _groupe, _setup


def _reagir(client, message_id, compte_id, emoji):
    return client.put(f"/messages/{message_id}/reaction", json={"compte_id": compte_id, "emoji": emoji})


def test_reaction_comme_whatsapp(client, db_session):
    from app.main import evenements_client

    ecole, _, prof, eleve, cours = _setup(db_session)
    conv = _groupe(client, ecole, cours)
    message = _envoyer(client, conv["id"], prof.id, "Stage samedi").json()
    assert message["reactions"] == []

    # Shows live, with the name, in everyone's thread.
    queue = evenements_client.abonner(prof.id)
    try:
        assert _reagir(client, message["id"], eleve.id, "👍").status_code == 200
        maj = queue.get_nowait()
        assert maj["type"] == "message_maj"
        assert maj["message"]["reactions"] == [{"emoji": "👍", "member_id": eleve.id, "name": "Léon Perrin"}]
    finally:
        evenements_client.desabonner(prof.id, queue)

    # One per person: another replaces it; the author reacts too.
    assert [r["emoji"] for r in _reagir(client, message["id"], eleve.id, "❤️").json()["reactions"]] == ["❤️"]
    deux = _reagir(client, message["id"], prof.id, "😂").json()["reactions"]
    assert [(r["emoji"], r["member_id"]) for r in deux] == [("❤️", eleve.id), ("😂", prof.id)]

    # None withdraws it; the thread shows what is left.
    _reagir(client, message["id"], eleve.id, None)
    liste = client.get(f"/conversations/{conv['id']}/messages").json()
    assert [r["member_id"] for r in liste[-1]["reactions"]] == [prof.id]


def test_seulement_les_membres_et_pas_un_message_supprime(client, db_session):
    ecole, admin, prof, eleve, cours = _setup(db_session)
    dm = client.post("/dm", params={"ecole_id": ecole.id, "compte_a_id": admin.id, "compte_b_id": prof.id}).json()
    autre = _envoyer(client, dm["id"], admin.id, "Entre nous").json()
    assert _reagir(client, autre["id"], eleve.id, "👍").status_code == 403
    assert _reagir(client, autre["id"], prof.id, "x" * 17).status_code == 400

    client.delete(f"/messages/{autre['id']}", params={"compte_id": admin.id})
    assert _reagir(client, autre["id"], prof.id, "👍").status_code == 404
