"""Tests du module videos (voir spec/SPEC.md §6.8)."""

from pathlib import Path

from choregraphies import Choregraphies
from comptes import Comptes
from cours import CoursService
from ecoles import Ecoles
from videos import DOSSIER_VIDEOS_LIVE, chemin_relatif, dossier_ecole

# Réutilise un vrai fichier de démo (déjà committé, voir
# backend/videos_reference/) comme fixture d'upload — pas besoin d'un
# fichier vidéo dédié aux tests.
_FICHIER_DEMO = (
    Path(__file__).resolve().parents[1] / "videos_reference" / "1" / "bang-bang-lent.mp4"
)


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


def test_detacher_une_video_dune_choregraphie(client, db_session):
    """Régression : Videos.update() ignorait toute valeur None (le
    receiver filtre déjà via exclude_unset=True, donc None ici veut dire
    "remettre à vide", pas "non fourni") — détaguer une vidéo en envoyant
    choregraphie_id=null ne faisait rien. Bug signalé : dans Chorégraphie,
    "on ne peut prendre que les vidéos qui sont taguées pour cette
    chorégraphie" (le detacher pour la retaguer ailleurs ne marchait pas)."""
    _, cours, choregraphie, admin = _setup(db_session)
    video = client.post(
        f"/cours/{cours.id}/videos",
        json={
            "nom": "Prise 1",
            "lien_fichier": "/videos/1.mp4",
            "uploaded_by": admin.id,
            "choregraphie_id": choregraphie.id,
        },
    ).json()
    assert video["choregraphie_id"] == choregraphie.id

    reponse = client.put(f"/videos/{video['id']}", json={"choregraphie_id": None})
    assert reponse.status_code == 200
    assert reponse.json()["choregraphie_id"] is None


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


def test_usage_ecole(client, db_session):
    """Panneau "Usage vidéo" (Admin > École) : Go utilisés, minutes de
    vidéo, top 10 par taille décroissante. Deux vrais fichiers écrits sur
    le disque (taille lue à la demande, pas stockée) + une vidéo sans
    fichier (lien_fichier vide, doit être ignorée) + une vidéo avec un
    lien_fichier renseigné mais dont le fichier est absent du disque
    (ignorée sans erreur, voir usage_ecole)."""
    ecole, cours, _, admin = _setup(db_session)

    petit = dossier_ecole(ecole.id) / "petit.mp4"
    grand = dossier_ecole(ecole.id) / "grand.mp4"
    petit.write_bytes(b"x" * 1000)
    grand.write_bytes(b"x" * 5000)
    try:
        client.post(
            f"/cours/{cours.id}/videos",
            json={
                "nom": "Petite prise",
                "lien_fichier": chemin_relatif(ecole.id, "petit.mp4"),
                "uploaded_by": admin.id,
                "duree_secondes": 10,
            },
        )
        client.post(
            f"/cours/{cours.id}/videos",
            json={
                "nom": "Grande prise",
                "lien_fichier": chemin_relatif(ecole.id, "grand.mp4"),
                "uploaded_by": admin.id,
                "duree_secondes": 20,
            },
        )
        # Sans fichier réel : ignorée (comme une chorégraphie "vidéo" sans
        # fichier associé, voir seed.py).
        client.post(
            f"/cours/{cours.id}/videos",
            json={"nom": "Sans fichier", "lien_fichier": "", "uploaded_by": admin.id},
        )
        # lien_fichier renseigné mais fichier absent du disque.
        client.post(
            f"/cours/{cours.id}/videos",
            json={
                "nom": "Fichier disparu",
                "lien_fichier": chemin_relatif(ecole.id, "disparu.mp4"),
                "uploaded_by": admin.id,
            },
        )

        reponse = client.get(f"/ecoles/{ecole.id}/videos/usage")
        assert reponse.status_code == 200
        donnees = reponse.json()
        assert donnees["total_octets"] == 6000
        assert donnees["total_secondes"] == 30
        assert [v["titre"] for v in donnees["top_videos"]] == ["Grande prise", "Petite prise"]
        assert donnees["top_videos"][0]["cours"] == "Eveil"
        assert donnees["top_videos"][0]["taille_octets"] == 5000
        assert donnees["top_videos"][0]["duree_secondes"] == 20
    finally:
        petit.unlink(missing_ok=True)
        grand.unlink(missing_ok=True)


def test_supprimer_video_efface_le_fichier_et_la_vignette(client, db_session):
    """Demande : "attention il faut nettoyer les tables qui référencent
    ces vidéos" — vérifié qu'aucune table n'a de FK vers videos.id (pas de
    nettoyage relationnel à faire), mais le vrai risque d'orphelin est le
    FICHIER (et sa vignette) sur le disque : sans ça, supprimer une vidéo
    depuis le panneau "Usage vidéo" ne libérait jamais l'espace compté."""
    ecole, cours, _, admin = _setup(db_session)
    fichier = dossier_ecole(ecole.id) / "a-supprimer.mp4"
    poster = dossier_ecole(ecole.id) / "a-supprimer.jpg"
    fichier.write_bytes(b"x" * 100)
    poster.write_bytes(b"x" * 10)

    video = client.post(
        f"/cours/{cours.id}/videos",
        json={
            "nom": "Prise à supprimer",
            "lien_fichier": chemin_relatif(ecole.id, "a-supprimer.mp4"),
            "poster": chemin_relatif(ecole.id, "a-supprimer.jpg"),
            "uploaded_by": admin.id,
        },
    ).json()

    assert client.delete(f"/videos/{video['id']}").status_code == 204
    assert not fichier.exists()
    assert not poster.exists()


def test_usage_ecole_indique_la_choregraphie_liee(client, db_session):
    """Demande : afficher, pour chaque vidéo, la chorégraphie liée si
    elle existe."""
    ecole, cours, choregraphie, admin = _setup(db_session)
    fichier = dossier_ecole(ecole.id) / "taguee.mp4"
    fichier.write_bytes(b"x" * 100)
    try:
        client.post(
            f"/cours/{cours.id}/videos",
            json={
                "nom": "Prise taguée",
                "lien_fichier": chemin_relatif(ecole.id, "taguee.mp4"),
                "uploaded_by": admin.id,
                "choregraphie_id": choregraphie.id,
            },
        )
        donnees = client.get(f"/ecoles/{ecole.id}/videos/usage").json()
        ligne = next(v for v in donnees["top_videos"] if v["titre"] == "Prise taguée")
        assert ligne["choregraphie"] == choregraphie.nom
    finally:
        fichier.unlink(missing_ok=True)


def test_usage_ecole_sans_cours(client, db_session):
    ecole = Ecoles().create(db_session, nom="Vide", code_postal="00000")
    reponse = client.get(f"/ecoles/{ecole.id}/videos/usage")
    assert reponse.status_code == 200
    assert reponse.json() == {"total_octets": 0, "total_secondes": 0, "top_videos": []}


def test_upload_reel(client, db_session):
    """Vrai upload (voir videos.py : creer_avec_upload) — mutualisé
    entre l'écran Vidéo et le détail d'une chorégraphie."""
    ecole, cours, choregraphie, admin = _setup(db_session)

    with open(_FICHIER_DEMO, "rb") as f:
        reponse = client.post(
            f"/cours/{cours.id}/videos/upload",
            data={
                "nom": "Upload test",
                "uploaded_by": str(admin.id),
                "description": "Une description",
                "choregraphie_id": str(choregraphie.id),
            },
            files={"fichier": ("bang-bang-lent.mp4", f, "video/mp4")},
        )
    assert reponse.status_code == 201
    video = reponse.json()
    try:
        assert video["nom"] == "Upload test"
        assert video["description"] == "Une description"
        assert video["choregraphie_id"] == choregraphie.id
        # Vraie durée mesurée (voir duree.py) — même fichier que
        # test_usage_ecole_indique_la_choregraphie_liee (22s).
        assert video["duree_secondes"] == 22
        assert video["poster"] is not None

        chemin_disque = DOSSIER_VIDEOS_LIVE / video["lien_fichier"]
        chemin_poster_disque = DOSSIER_VIDEOS_LIVE / video["poster"]
        assert chemin_disque.exists()
        assert chemin_poster_disque.exists()
    finally:
        (DOSSIER_VIDEOS_LIVE / video["lien_fichier"]).unlink(missing_ok=True)
        if video["poster"]:
            (DOSSIER_VIDEOS_LIVE / video["poster"]).unlink(missing_ok=True)


def test_upload_cours_introuvable(client, db_session):
    with open(_FICHIER_DEMO, "rb") as f:
        reponse = client.post(
            "/cours/999/videos/upload",
            data={"nom": "X", "uploaded_by": "1"},
            files={"fichier": ("bang-bang-lent.mp4", f, "video/mp4")},
        )
    assert reponse.status_code == 404
