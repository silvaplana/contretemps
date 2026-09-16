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


def _ecrire_bloc(client, upload_id, decalage, donnees):
    return client.put(
        f"/videos/televersements/{upload_id}",
        content=donnees,
        headers={"X-Decalage": str(decalage), "Content-Type": "application/octet-stream"},
    )


def test_upload_par_blocs_puis_ajouter_apres_la_fin_de_lenvoi(client, db_session):
    """Cas simple : tous les blocs arrivent avant le clic "Ajouter" (voir
    videos.py : Televersement, finaliser)."""
    ecole, cours, choregraphie, admin = _setup(db_session)
    contenu = _FICHIER_DEMO.read_bytes()

    ouverture = client.post(
        f"/cours/{cours.id}/videos/televersements",
        json={"extension": ".mp4", "octets_total": len(contenu)},
    )
    assert ouverture.status_code == 201
    upload_id = ouverture.json()["id"]

    moitie = len(contenu) // 2
    r1 = _ecrire_bloc(client, upload_id, 0, contenu[:moitie])
    assert r1.status_code == 200
    assert r1.json() == {
        "id": upload_id, "octets_recus": moitie, "octets_total": len(contenu), "complet": False
    }
    r2 = _ecrire_bloc(client, upload_id, moitie, contenu[moitie:])
    assert r2.status_code == 200
    assert r2.json()["complet"] is True

    reponse = client.post(
        f"/cours/{cours.id}/videos/depuis-televersement",
        json={
            "upload_id": upload_id,
            "nom": "Upload test",
            "uploaded_by": admin.id,
            "description": "Une description",
            "choregraphie_id": choregraphie.id,
        },
    )
    assert reponse.status_code == 201
    video = reponse.json()
    try:
        assert video["nom"] == "Upload test"
        assert video["choregraphie_id"] == choregraphie.id
        assert video["statut"] == "complete"
        # Vraie durée mesurée (voir duree.py) — même fichier que
        # test_usage_ecole_indique_la_choregraphie_liee (22s).
        assert video["duree_secondes"] == 22
        assert video["poster"] is not None
        assert (DOSSIER_VIDEOS_LIVE / video["lien_fichier"]).exists()
        assert (DOSSIER_VIDEOS_LIVE / video["poster"]).exists()
        # La session reste (jamais supprimée par _finaliser_fichier, voir
        # son docstring) — juste inerte, sert à l'idempotence de finaliser.
        assert client.get(f"/videos/televersements/{upload_id}").json()["complet"] is True
    finally:
        (DOSSIER_VIDEOS_LIVE / video["lien_fichier"]).unlink(missing_ok=True)
        if video["poster"]:
            (DOSSIER_VIDEOS_LIVE / video["poster"]).unlink(missing_ok=True)


def test_ajouter_avant_la_fin_de_lenvoi_puis_le_dernier_bloc_finalise(client, db_session):
    """Cas WhatsApp : l'admin clique "Ajouter" (voir spec) pendant que
    l'envoi continue en tâche de fond — la ligne existe tout de suite en
    'en_cours', le DERNIER bloc la fait passer à 'complete' sans appel
    supplémentaire."""
    ecole, cours, _, admin = _setup(db_session)
    contenu = _FICHIER_DEMO.read_bytes()

    upload_id = client.post(
        f"/cours/{cours.id}/videos/televersements",
        json={"extension": ".mp4", "octets_total": len(contenu)},
    ).json()["id"]
    moitie = len(contenu) // 2
    _ecrire_bloc(client, upload_id, 0, contenu[:moitie])

    reponse = client.post(
        f"/cours/{cours.id}/videos/depuis-televersement",
        json={"upload_id": upload_id, "nom": "En cours", "uploaded_by": admin.id},
    )
    assert reponse.status_code == 201
    video = reponse.json()
    assert video["statut"] == "en_cours"
    assert video["lien_fichier"] == ""
    assert video["poster"] is None

    r2 = _ecrire_bloc(client, upload_id, moitie, contenu[moitie:])
    assert r2.status_code == 200
    assert r2.json()["complet"] is True

    try:
        fini = client.get(f"/videos/{video['id']}").json()
        assert fini["statut"] == "complete"
        assert fini["lien_fichier"] != ""
        assert fini["duree_secondes"] == 22
        assert (DOSSIER_VIDEOS_LIVE / fini["lien_fichier"]).exists()
    finally:
        fini = client.get(f"/videos/{video['id']}").json()
        (DOSSIER_VIDEOS_LIVE / fini["lien_fichier"]).unlink(missing_ok=True)
        if fini["poster"]:
            (DOSSIER_VIDEOS_LIVE / fini["poster"]).unlink(missing_ok=True)


def test_decalage_invalide_renvoie_le_bon_decalage(client, db_session):
    """Coupure réseau en plein envoi (voir spec : "gestion des
    interruptions") : le client retente un bloc au mauvais endroit — 409
    avec le VRAI décalage, pour qu'il resynchronise plutôt que de deviner."""
    _, cours, _, _ = _setup(db_session)
    upload_id = client.post(
        f"/cours/{cours.id}/videos/televersements",
        json={"extension": ".mp4", "octets_total": 100},
    ).json()["id"]
    _ecrire_bloc(client, upload_id, 0, b"x" * 50)

    reponse = _ecrire_bloc(client, upload_id, 30, b"y" * 20)  # décalage faux (devrait être 50)
    assert reponse.status_code == 409
    assert reponse.json()["detail"]["octets_recus"] == 50


def test_annuler_televersement_nettoie_le_fichier_partiel(client, db_session):
    """Spec : "l'appui sur annuler arrête tout, il faudra nettoyer
    l'upload" — y compris si "Ajouter" avait déjà été cliqué (voir
    Videos.annuler_televersement)."""
    _, cours, _, admin = _setup(db_session)
    ecole = Ecoles().create(db_session, nom="Autre", code_postal="11111")
    upload_id = client.post(
        f"/cours/{cours.id}/videos/televersements",
        json={"extension": ".mp4", "octets_total": 100},
    ).json()["id"]
    _ecrire_bloc(client, upload_id, 0, b"x" * 50)

    video_id = client.post(
        f"/cours/{cours.id}/videos/depuis-televersement",
        json={"upload_id": upload_id, "nom": "Annulée", "uploaded_by": admin.id},
    ).json()["id"]

    assert client.delete(f"/videos/televersements/{upload_id}").status_code == 204
    # La ligne Video (créée en 'en_cours') est aussi supprimée.
    assert client.get(f"/videos/{video_id}").status_code == 404
    assert client.get(f"/videos/televersements/{upload_id}").status_code == 404
    _ = ecole  # juste pour vérifier qu'aucune fuite entre écoles n'affecte ce test


def test_finaliser_deux_fois_de_suite_ne_cree_pas_2_videos(client, db_session):
    """Double clic/double appel (voir AdminEleves.jsx pour un motif
    similaire) : renvoie la même ligne plutôt que d'en créer une 2e."""
    _, cours, _, admin = _setup(db_session)
    upload_id = client.post(
        f"/cours/{cours.id}/videos/televersements",
        json={"extension": ".mp4", "octets_total": 10},
    ).json()["id"]
    _ecrire_bloc(client, upload_id, 0, b"x" * 10)

    donnees = {"upload_id": upload_id, "nom": "Double", "uploaded_by": admin.id}
    v1 = client.post(f"/cours/{cours.id}/videos/depuis-televersement", json=donnees).json()
    v2 = client.post(f"/cours/{cours.id}/videos/depuis-televersement", json=donnees).json()
    assert v1["id"] == v2["id"]


def test_televersement_introuvable(client, db_session):
    _, cours, _, _ = _setup(db_session)
    assert _ecrire_bloc(client, "inconnu", 0, b"x").status_code == 404
    assert client.get("/videos/televersements/inconnu").status_code == 404
    assert client.delete("/videos/televersements/inconnu").status_code == 404
    reponse = client.post(
        f"/cours/{cours.id}/videos/depuis-televersement",
        json={"upload_id": "inconnu", "nom": "X", "uploaded_by": 1},
    )
    assert reponse.status_code == 404


def test_ouvrir_televersement_cours_introuvable(client, db_session):
    reponse = client.post(
        "/cours/999/videos/televersements", json={"extension": ".mp4", "octets_total": 10}
    )
    assert reponse.status_code == 404
