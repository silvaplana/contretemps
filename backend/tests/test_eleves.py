"""Tests du module eleves (voir spec/SPEC.md §6.4)."""

import datetime as dt

from ecoles import Ecoles
from eleves import calculer_age


def _creer_ecole(db_session):
    return Ecoles().create(db_session, nom="Contretemps", code_postal="83330")


def test_calculer_age():
    aujourdhui = dt.date(2026, 9, 9)
    # Anniversaire déjà passé cette année.
    assert calculer_age(dt.date(2020, 1, 1), aujourdhui) == 6
    # Anniversaire pas encore atteint cette année.
    assert calculer_age(dt.date(2020, 12, 31), aujourdhui) == 5
    assert calculer_age(None, aujourdhui) is None


def test_creer_puis_lister(client, db_session):
    ecole = _creer_ecole(db_session)
    reponse = client.post(
        "/eleves",
        params={"ecole_id": ecole.id},
        json={"nom": "Perrin", "prenom": "Léon", "date_naissance": "2018-05-10"},
    )
    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["nom"] == "Perrin"
    assert corps["date_naissance"] == "2018-05-10"
    assert corps["age"] is not None
    assert corps["statut_paiement"] == "en_cours"
    assert corps["montant_paye"] == 0
    assert corps["contacts"] == []

    reponse = client.get("/eleves", params={"ecole_id": ecole.id})
    assert reponse.status_code == 200
    assert len(reponse.json()) == 1


def test_obtenir_eleve_introuvable(client):
    assert client.get("/eleves/999").status_code == 404


def test_supprimer_eleve(client, db_session):
    ecole = _creer_ecole(db_session)
    creee = client.post(
        "/eleves", params={"ecole_id": ecole.id}, json={"nom": "Perrin", "prenom": "Léon"}
    ).json()
    client.post(f"/eleves/{creee['id']}/contacts", json={"nom": "Perrin", "prenom": "Alice"})

    assert client.delete(f"/eleves/{creee['id']}").status_code == 204
    assert client.get(f"/eleves/{creee['id']}").status_code == 404


def test_supprimer_eleve_retire_ses_inscriptions(client, db_session):
    """Cas vu en production : les inscriptions aux cours survivaient à la
    suppression de l'élève (4 lignes orphelines pour 2 comptes). Pire, un
    nouvel élève qui récupère le même id (SQLite réutilise le plus grand
    id supprimé) en héritait."""
    ecole = _creer_ecole(db_session)
    cours = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Éveil"}).json()
    choregraphie = client.post(
        f"/cours/{cours['id']}/choregraphies", json={"nom": "Spectacle"}
    ).json()
    parti = client.post(
        "/eleves", params={"ecole_id": ecole.id}, json={"nom": "Perrin", "prenom": "Léon"}
    ).json()
    client.post(f"/cours/{cours['id']}/eleves/{parti['id']}")
    client.post(f"/choregraphies/{choregraphie['id']}/eleves/{parti['id']}")

    assert client.delete(f"/eleves/{parti['id']}").status_code == 204

    assert client.get(f"/cours/{cours['id']}/eleves").json() == []
    assert client.get(f"/choregraphies/{choregraphie['id']}/eleves").json() == []
    assert client.get("/cours-par-eleve", params={"ecole_id": ecole.id}).json() == {}

    nouveau = client.post(
        "/eleves", params={"ecole_id": ecole.id}, json={"nom": "Roux", "prenom": "Ana"}
    ).json()
    # Le scénario dangereux suppose que l'id soit bien réutilisé : on le
    # vérifie, sinon le test passerait sans rien prouver.
    assert nouveau["id"] == parti["id"]
    assert client.get(f"/eleves/{nouveau['id']}/cours").json() == []


def test_supprimer_eleve_introuvable(client):
    assert client.delete("/eleves/999").status_code == 404


def test_modifier_eleve_champs_compte_et_profil(client, db_session):
    ecole = _creer_ecole(db_session)
    creee = client.post(
        "/eleves", params={"ecole_id": ecole.id}, json={"nom": "Perrin", "prenom": "Léon"}
    ).json()

    reponse = client.put(
        f"/eleves/{creee['id']}",
        json={"telephone": "0600000000", "statut_paiement": "paye", "montant_paye": 150},
    )
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["telephone"] == "0600000000"
    assert corps["statut_paiement"] == "paye"
    assert corps["montant_paye"] == 150
    # Champs non touchés restent inchangés.
    assert corps["nom"] == "Perrin"


def test_modifier_eleve_introuvable(client):
    assert client.put("/eleves/999", json={"nom": "X"}).status_code == 404


def test_contacts_cycle_complet(client, db_session):
    ecole = _creer_ecole(db_session)
    eleve = client.post(
        "/eleves", params={"ecole_id": ecole.id}, json={"nom": "Perrin", "prenom": "Léon"}
    ).json()

    reponse = client.post(
        f"/eleves/{eleve['id']}/contacts",
        json={"nom": "Perrin", "prenom": "Alice", "lien": "Mère", "telephone": "0611111111"},
    )
    assert reponse.status_code == 201
    contact = reponse.json()
    assert contact["eleve_id"] == eleve["id"]

    # Deuxième contact (parents séparés, voir §6.4).
    client.post(
        f"/eleves/{eleve['id']}/contacts",
        json={"nom": "Perrin", "prenom": "Bruno", "lien": "Père"},
    )
    assert len(client.get(f"/eleves/{eleve['id']}/contacts").json()) == 2

    reponse = client.put(f"/contacts/{contact['id']}", json={"telephone": "0622222222"})
    assert reponse.status_code == 200
    assert reponse.json()["telephone"] == "0622222222"

    assert client.delete(f"/contacts/{contact['id']}").status_code == 204
    assert len(client.get(f"/eleves/{eleve['id']}/contacts").json()) == 1


def test_contact_introuvable(client):
    assert client.put("/contacts/999", json={"nom": "X"}).status_code == 404
    assert client.delete("/contacts/999").status_code == 404
