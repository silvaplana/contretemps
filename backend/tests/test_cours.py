"""Tests du module cours (voir spec/SPEC.md §6.5)."""

from comptes import Comptes
from ecoles import Ecoles


def _creer_ecole_et_comptes(db_session):
    ecoles = Ecoles()
    comptes = Comptes()
    ecole = ecoles.create(db_session, nom="Contretemps", code_postal="83330")
    prof = comptes.create(
        db_session, ecole_id=ecole.id, role="professeur", nom="Pesenti", prenom="Marie-Laure"
    )
    eleve = comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="Perrin", prenom="Léon")
    return ecole, prof, eleve


def test_creer_puis_lister(client, db_session):
    ecole, _, _ = _creer_ecole_et_comptes(db_session)
    reponse = client.post(
        "/cours",
        params={"ecole_id": ecole.id},
        json={"nom": "Eveil", "jour": "Mercredi", "heure_debut": "17:00", "heure_fin": "18:00"},
    )
    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["nom"] == "Eveil"
    assert corps["ecole_id"] == ecole.id

    reponse = client.get("/cours", params={"ecole_id": ecole.id})
    assert reponse.status_code == 200
    assert len(reponse.json()) == 1


def test_modifier_cours(client, db_session):
    ecole, _, _ = _creer_ecole_et_comptes(db_session)
    creee = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Eveil"}).json()
    reponse = client.put(f"/cours/{creee['id']}", json={"salle": "Salle 1"})
    assert reponse.status_code == 200
    assert reponse.json()["salle"] == "Salle 1"
    assert reponse.json()["nom"] == "Eveil"


def test_supprimer_cours(client, db_session):
    ecole, _, _ = _creer_ecole_et_comptes(db_session)
    creee = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Eveil"}).json()
    assert client.delete(f"/cours/{creee['id']}").status_code == 204
    assert client.get(f"/cours/{creee['id']}").status_code == 404


def test_cours_introuvable(client):
    assert client.get("/cours/999").status_code == 404
    assert client.put("/cours/999", json={"nom": "X"}).status_code == 404
    assert client.delete("/cours/999").status_code == 404


def test_ajouter_et_retirer_professeur(client, db_session):
    ecole, prof, _ = _creer_ecole_et_comptes(db_session)
    creee = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Eveil"}).json()

    assert client.post(f"/cours/{creee['id']}/professeurs/{prof.id}").status_code == 204
    reponse = client.get(f"/cours/{creee['id']}/professeurs")
    assert reponse.status_code == 200
    assert [p["id"] for p in reponse.json()] == [prof.id]

    assert client.delete(f"/cours/{creee['id']}/professeurs/{prof.id}").status_code == 204
    assert client.get(f"/cours/{creee['id']}/professeurs").json() == []


def test_inscrire_et_desinscrire_eleve(client, db_session):
    ecole, _, eleve = _creer_ecole_et_comptes(db_session)
    creee = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Eveil"}).json()

    assert client.post(f"/cours/{creee['id']}/eleves/{eleve.id}").status_code == 204
    reponse = client.get(f"/cours/{creee['id']}/eleves")
    assert reponse.status_code == 200
    assert [e["id"] for e in reponse.json()] == [eleve.id]

    assert client.delete(f"/cours/{creee['id']}/eleves/{eleve.id}").status_code == 204
    assert client.get(f"/cours/{creee['id']}/eleves").json() == []


def test_inscrire_eleve_deux_fois_ne_duplique_pas(client, db_session):
    ecole, _, eleve = _creer_ecole_et_comptes(db_session)
    creee = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Eveil"}).json()

    client.post(f"/cours/{creee['id']}/eleves/{eleve.id}")
    client.post(f"/cours/{creee['id']}/eleves/{eleve.id}")
    assert len(client.get(f"/cours/{creee['id']}/eleves").json()) == 1


def test_cours_de_leleve(client, db_session):
    """Sens inverse de /cours/{id}/eleves — voir Admin > Élèves (colonne
    "cours suivis")."""
    ecole, _, eleve = _creer_ecole_et_comptes(db_session)
    c1 = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Eveil"}).json()
    c2 = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Jazz"}).json()
    client.post(f"/cours/{c1['id']}/eleves/{eleve.id}")

    reponse = client.get(f"/eleves/{eleve.id}/cours")
    assert reponse.status_code == 200
    assert [c["id"] for c in reponse.json()] == [c1["id"]]
    assert c2["id"] not in [c["id"] for c in reponse.json()]
