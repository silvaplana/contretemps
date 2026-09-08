"""Tests du module presence (voir spec/SPEC.md §6.6)."""

from comptes import Comptes
from cours import CoursService
from ecoles import Ecoles


def _setup(db_session):
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    comptes = Comptes()
    prof = comptes.create(
        db_session, ecole_id=ecole.id, role="professeur", nom="Pesenti", prenom="Marie-Laure"
    )
    eleve = comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="Perrin", prenom="Léon")
    cours = CoursService().create(
        db_session, ecole_id=ecole.id, nom="Eveil", heure_debut="17:00", heure_fin="18:00"
    )
    return ecole, prof, eleve, cours


def test_creer_seance_puis_lister(client, db_session):
    _, _, _, cours = _setup(db_session)
    reponse = client.post(f"/cours/{cours.id}/seances", json={"date": "2026-09-09"})
    assert reponse.status_code == 201
    assert reponse.json()["cours_id"] == cours.id

    reponse = client.get(f"/cours/{cours.id}/seances")
    assert reponse.status_code == 200
    assert len(reponse.json()) == 1


def test_seance_introuvable(client):
    assert client.get("/seances/999").status_code == 404
    assert client.delete("/seances/999").status_code == 404


def test_presence_eleve_par_defaut_present(client, db_session):
    """Voir consigne : par défaut tous les élèves à présent."""
    _, _, eleve, cours = _setup(db_session)
    seance = client.post(f"/cours/{cours.id}/seances", json={"date": "2026-09-09"}).json()

    reponse = client.put(
        f"/seances/{seance['id']}/eleves/{eleve.id}", json={"statut": "present"}
    )
    assert reponse.status_code == 200
    assert reponse.json()["statut"] == "present"

    reponse = client.put(
        f"/seances/{seance['id']}/eleves/{eleve.id}", json={"statut": "absent"}
    )
    assert reponse.status_code == 200
    assert reponse.json()["statut"] == "absent"
    # Upsert : toujours une seule ligne pour cet élève à cette séance.
    assert len(client.get(f"/seances/{seance['id']}/eleves").json()) == 1


def test_presence_prof_deduite_des_heures(client, db_session):
    _, prof, _, cours = _setup(db_session)
    seance = client.post(f"/cours/{cours.id}/seances", json={"date": "2026-09-09"}).json()

    # Rien saisi -> absent, "–" côté frontend (pas testé ici, juste None).
    reponse = client.get(f"/seances/{seance['id']}/profs")
    assert reponse.json() == []

    reponse = client.put(
        f"/seances/{seance['id']}/profs/{prof.id}",
        json={"heure_debut_reelle": "17:00", "heure_fin_reelle": "18:00"},
    )
    assert reponse.status_code == 200
    assert reponse.json()["statut"] == "present"

    # Retard : heure réelle après l'heure théorique du cours (17:00).
    reponse = client.put(
        f"/seances/{seance['id']}/profs/{prof.id}",
        json={"heure_debut_reelle": "17:10"},
    )
    assert reponse.json()["statut"] == "retard"


def test_heures_professeur_agregees(client, db_session):
    _, prof, _, cours = _setup(db_session)
    seance1 = client.post(f"/cours/{cours.id}/seances", json={"date": "2026-09-09"}).json()
    seance2 = client.post(f"/cours/{cours.id}/seances", json={"date": "2026-09-16"}).json()

    client.put(
        f"/seances/{seance1['id']}/profs/{prof.id}",
        json={"heure_debut_reelle": "17:00", "heure_fin_reelle": "18:00", "depassement_minutes": 10},
    )
    client.put(
        f"/seances/{seance2['id']}/profs/{prof.id}",
        json={"heure_debut_reelle": "17:00", "heure_fin_reelle": "18:30"},
    )

    reponse = client.get(f"/profs/{prof.id}/heures")
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["minutes_total"] == 60 + 90
    assert corps["minutes_depassement"] == 10


def test_supprimer_seance_nettoie_les_presences(client, db_session):
    _, prof, eleve, cours = _setup(db_session)
    seance = client.post(f"/cours/{cours.id}/seances", json={"date": "2026-09-09"}).json()
    client.put(f"/seances/{seance['id']}/eleves/{eleve.id}", json={"statut": "present"})
    client.put(f"/seances/{seance['id']}/profs/{prof.id}", json={"heure_debut_reelle": "17:00"})

    assert client.delete(f"/seances/{seance['id']}").status_code == 204
    assert client.get(f"/seances/{seance['id']}").status_code == 404
