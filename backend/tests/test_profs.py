"""Tests du module profs (voir spec/SPEC.md §6.3 : pas de champ propre)."""

from ecoles import Ecoles


def _creer_ecole(db_session):
    return Ecoles().create(db_session, nom="Contretemps", code_postal="83330")


def test_creer_puis_lister(client, db_session):
    ecole = _creer_ecole(db_session)
    reponse = client.post(
        "/profs", params={"ecole_id": ecole.id}, json={"nom": "Pesenti", "prenom": "Marie-Laure"}
    )
    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["nom"] == "Pesenti"
    assert corps["cours_ids"] == []

    reponse = client.get("/profs", params={"ecole_id": ecole.id})
    assert reponse.status_code == 200
    assert len(reponse.json()) == 1


def test_prof_introuvable(client):
    assert client.get("/profs/999").status_code == 404
    assert client.put("/profs/999", json={"nom": "X"}).status_code == 404
    assert client.delete("/profs/999").status_code == 404


def test_modifier_prof(client, db_session):
    ecole = _creer_ecole(db_session)
    creee = client.post(
        "/profs", params={"ecole_id": ecole.id}, json={"nom": "Pesenti", "prenom": "Marie-Laure"}
    ).json()
    reponse = client.put(f"/profs/{creee['id']}", json={"email": "ml.pesenti@x.fr"})
    assert reponse.status_code == 200
    assert reponse.json()["email"] == "ml.pesenti@x.fr"
    assert reponse.json()["nom"] == "Pesenti"


def test_cours_ids_reflete_le_module_cours(client, db_session):
    """L'assignation cours<->prof passe par les routes du module cours,
    pas par profs — mais /profs doit refléter le résultat."""
    ecole = _creer_ecole(db_session)
    prof = client.post(
        "/profs", params={"ecole_id": ecole.id}, json={"nom": "Pesenti", "prenom": "Marie-Laure"}
    ).json()
    cours = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Eveil"}).json()

    client.post(f"/cours/{cours['id']}/professeurs/{prof['id']}")
    reponse = client.get(f"/profs/{prof['id']}")
    assert reponse.json()["cours_ids"] == [cours["id"]]


def test_supprimer_prof_le_retire_de_ses_cours(client, db_session):
    ecole = _creer_ecole(db_session)
    prof = client.post(
        "/profs", params={"ecole_id": ecole.id}, json={"nom": "Pesenti", "prenom": "Marie-Laure"}
    ).json()
    cours = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Eveil"}).json()
    client.post(f"/cours/{cours['id']}/professeurs/{prof['id']}")

    assert client.delete(f"/profs/{prof['id']}").status_code == 204
    assert client.get(f"/profs/{prof['id']}").status_code == 404
    assert client.get(f"/cours/{cours['id']}/professeurs").json() == []
