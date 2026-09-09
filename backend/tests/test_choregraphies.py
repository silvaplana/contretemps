"""Tests du module choregraphies (voir spec/SPEC.md §6.7)."""

from comptes import Comptes
from cours import CoursService
from ecoles import Ecoles


def _setup(db_session):
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    comptes = Comptes()
    eleve_inscrit = comptes.create(
        db_session, ecole_id=ecole.id, role="eleve", nom="Perrin", prenom="Léon"
    )
    eleve_hors_cours = comptes.create(
        db_session, ecole_id=ecole.id, role="eleve", nom="Thomas", prenom="Simon"
    )
    cours = CoursService().create(db_session, ecole_id=ecole.id, nom="Eveil")
    CoursService().inscrire_eleve(db_session, cours.id, eleve_inscrit.id)
    return ecole, cours, eleve_inscrit, eleve_hors_cours


def test_creer_puis_lister(client, db_session):
    _, cours, _, _ = _setup(db_session)
    reponse = client.post(
        f"/cours/{cours.id}/choregraphies",
        json={"nom": "Spectacle fin d'année", "costume": "Robe bleue"},
    )
    assert reponse.status_code == 201
    assert reponse.json()["cours_id"] == cours.id

    reponse = client.get(f"/cours/{cours.id}/choregraphies")
    assert reponse.status_code == 200
    assert len(reponse.json()) == 1


def test_choregraphie_introuvable(client):
    assert client.get("/choregraphies/999").status_code == 404
    assert client.put("/choregraphies/999", json={"nom": "X"}).status_code == 404
    assert client.delete("/choregraphies/999").status_code == 404


def test_ajouter_eleve_inscrit_au_cours(client, db_session):
    _, cours, eleve_inscrit, _ = _setup(db_session)
    choregraphie = client.post(
        f"/cours/{cours.id}/choregraphies", json={"nom": "Spectacle"}
    ).json()

    reponse = client.post(f"/choregraphies/{choregraphie['id']}/eleves/{eleve_inscrit.id}")
    assert reponse.status_code == 204
    participants = client.get(f"/choregraphies/{choregraphie['id']}/eleves").json()
    assert [p["id"] for p in participants] == [eleve_inscrit.id]


def test_refuse_eleve_non_inscrit_au_cours(client, db_session):
    """Voir §6.7 : "seuls les élèves déjà inscrits au cours peuvent y
    être ajoutés"."""
    _, cours, _, eleve_hors_cours = _setup(db_session)
    choregraphie = client.post(
        f"/cours/{cours.id}/choregraphies", json={"nom": "Spectacle"}
    ).json()

    reponse = client.post(f"/choregraphies/{choregraphie['id']}/eleves/{eleve_hors_cours.id}")
    assert reponse.status_code == 409
    assert client.get(f"/choregraphies/{choregraphie['id']}/eleves").json() == []


def test_retirer_eleve(client, db_session):
    _, cours, eleve_inscrit, _ = _setup(db_session)
    choregraphie = client.post(
        f"/cours/{cours.id}/choregraphies", json={"nom": "Spectacle"}
    ).json()
    client.post(f"/choregraphies/{choregraphie['id']}/eleves/{eleve_inscrit.id}")

    assert (
        client.delete(f"/choregraphies/{choregraphie['id']}/eleves/{eleve_inscrit.id}").status_code
        == 204
    )
    assert client.get(f"/choregraphies/{choregraphie['id']}/eleves").json() == []
