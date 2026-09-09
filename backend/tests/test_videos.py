"""Tests du module videos (voir spec/SPEC.md §6.8)."""

from choregraphies import Choregraphies
from comptes import Comptes
from cours import CoursService
from ecoles import Ecoles


def _setup(db_session):
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    admin = Comptes().create(
        db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia"
    )
    cours = CoursService().create(db_session, ecole_id=ecole.id, nom="Eveil")
    choregraphie = Choregraphies(cours=CoursService()).create(
        db_session, cours.id, nom="Spectacle"
    )
    return ecole, cours, choregraphie, admin


def test_creer_puis_lister_par_cours_tri_par_date(client, db_session):
    _, cours, _, admin = _setup(db_session)
    v1 = client.post(
        f"/cours/{cours.id}/videos",
        json={"nom": "Prise 1", "lien_fichier": "/videos/1.mp4", "uploaded_by": admin.id},
    ).json()
    v2 = client.post(
        f"/cours/{cours.id}/videos",
        json={"nom": "Prise 2", "lien_fichier": "/videos/2.mp4", "uploaded_by": admin.id},
    ).json()

    reponse = client.get(f"/cours/{cours.id}/videos")
    assert reponse.status_code == 200
    # Plus récente en premier (voir §6.8) — v2 créée après v1.
    assert [v["id"] for v in reponse.json()] == [v2["id"], v1["id"]]


def test_video_introuvable(client):
    assert client.get("/videos/999").status_code == 404
    assert client.put("/videos/999", json={"nom": "X"}).status_code == 404
    assert client.delete("/videos/999").status_code == 404


def test_lister_par_choregraphie_tri_par_ordre_manuel(client, db_session):
    _, cours, choregraphie, admin = _setup(db_session)
    v1 = client.post(
        f"/cours/{cours.id}/videos",
        json={
            "nom": "Prise 1",
            "lien_fichier": "/videos/1.mp4",
            "uploaded_by": admin.id,
            "choregraphie_id": choregraphie.id,
        },
    ).json()
    v2 = client.post(
        f"/cours/{cours.id}/videos",
        json={
            "nom": "Prise 2",
            "lien_fichier": "/videos/2.mp4",
            "uploaded_by": admin.id,
            "choregraphie_id": choregraphie.id,
        },
    ).json()

    # Réordonne : v2 avant v1, malgré une création dans l'autre sens.
    reponse = client.put(
        f"/choregraphies/{choregraphie.id}/videos/ordre",
        json={"ordre_video_ids": [v2["id"], v1["id"]]},
    )
    assert reponse.status_code == 204

    reponse = client.get(f"/choregraphies/{choregraphie.id}/videos")
    assert [v["id"] for v in reponse.json()] == [v2["id"], v1["id"]]


def test_modifier_et_supprimer_video(client, db_session):
    _, cours, _, admin = _setup(db_session)
    video = client.post(
        f"/cours/{cours.id}/videos",
        json={"nom": "Prise 1", "lien_fichier": "/videos/1.mp4", "uploaded_by": admin.id},
    ).json()

    reponse = client.put(f"/videos/{video['id']}", json={"description": "Répétition du 9/9"})
    assert reponse.status_code == 200
    assert reponse.json()["description"] == "Répétition du 9/9"

    assert client.delete(f"/videos/{video['id']}").status_code == 204
    assert client.get(f"/videos/{video['id']}").status_code == 404


def test_poster_optionnel(client, db_session):
    """Voir §6.8 : vignette ajoutée pour l'affichage mobile (Chrome/Brave/
    Samsung Internet Android n'affichent pas la 1re image sans elle)."""
    _, cours, _, admin = _setup(db_session)
    sans_poster = client.post(
        f"/cours/{cours.id}/videos",
        json={"nom": "Prise 1", "lien_fichier": "/videos/1.mp4", "uploaded_by": admin.id},
    ).json()
    assert sans_poster["poster"] is None

    avec_poster = client.post(
        f"/cours/{cours.id}/videos",
        json={
            "nom": "Prise 2",
            "lien_fichier": "/videos/2.mp4",
            "poster": "/videos/2.jpg",
            "uploaded_by": admin.id,
        },
    ).json()
    assert avec_poster["poster"] == "/videos/2.jpg"

    reponse = client.put(f"/videos/{sans_poster['id']}", json={"poster": "/videos/1.jpg"})
    assert reponse.json()["poster"] == "/videos/1.jpg"
