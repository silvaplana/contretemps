"""Tests du module ecoles (voir conftest.py pour la fixture `client`,
base isolée par test)."""


def test_creer_puis_lister(client):
    reponse = client.post("/ecoles", json={"nom": "Contretemps", "code_postal": "83330"})
    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["nom"] == "Contretemps"
    assert corps["code_acces_admin"] == "ADMIN_CONTRETEMPS_2026"

    reponse = client.get("/ecoles")
    assert reponse.status_code == 200
    assert len(reponse.json()) == 1


def test_creer_deux_ecoles_meme_nom_villes_differentes(client):
    """Le nom seul n'est pas unique (voir spec §6.1) : deux écoles peuvent
    partager le même nom si leur code postal diffère."""
    r1 = client.post("/ecoles", json={"nom": "Contretemps", "code_postal": "83330"})
    r2 = client.post("/ecoles", json={"nom": "Contretemps", "code_postal": "75001"})
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] != r2.json()["id"]


def test_creer_doublon_nom_et_code_postal_refuse(client):
    client.post("/ecoles", json={"nom": "Contretemps", "code_postal": "83330"})
    reponse = client.post("/ecoles", json={"nom": "Contretemps", "code_postal": "83330"})
    assert reponse.status_code == 409


def test_modifier_ecole(client):
    creee = client.post("/ecoles", json={"nom": "Contretemps", "code_postal": "83330"}).json()
    reponse = client.put(f"/ecoles/{creee['id']}", json={"code_acces_admin": "NOUVEAU"})
    assert reponse.status_code == 200
    assert reponse.json()["code_acces_admin"] == "NOUVEAU"
    # Les autres champs restent inchangés (exclude_unset).
    assert reponse.json()["nom"] == "Contretemps"


def test_ecole_introuvable(client):
    assert client.get("/ecoles/999").status_code == 404
    assert client.put("/ecoles/999", json={"nom": "X"}).status_code == 404
