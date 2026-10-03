"""Tests du module videos (voir spec/SPEC.md §6.8) — module générique : une
vidéo appartient à une école, et ne connaît ni cours ni chorégraphie (voir
tests/test_choregraphies.py pour leur rattachement)."""

from pathlib import Path

import pytest
from app.main import app, videos_client
from comptes import Comptes, rbac
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
    return ecole, admin


def _video(db_session, ecole, admin, **champs):
    champs.setdefault("nom", "Prise 1")
    champs.setdefault("lien_fichier", "")
    return videos_client.create(db_session, ecole_id=ecole.id, uploaded_by=admin.id, **champs)


def _ecrire_bloc(client, upload_id, decalage, donnees):
    return client.put(
        f"/videos/televersements/{upload_id}",
        content=donnees,
        headers={"X-Decalage": str(decalage), "Content-Type": "application/octet-stream"},
    )


def _ouvrir(client, ecole, octets_total):
    return client.post(
        f"/ecoles/{ecole.id}/videos/televersements",
        json={"extension": ".mp4", "octets_total": octets_total},
    )


def test_video_introuvable(client):
    assert client.get("/videos/999").status_code == 404
    assert client.put("/videos/999", json={"nom": "X"}).status_code == 404
    assert client.delete("/videos/999").status_code == 404


def test_obtenir_modifier_supprimer(client, db_session):
    ecole, admin = _setup(db_session)
    video = _video(db_session, ecole, admin, description="Avant")

    lue = client.get(f"/videos/{video.id}").json()
    assert (lue["nom"], lue["ecole_id"], lue["uploaded_by"]) == ("Prise 1", ecole.id, admin.id)
    # La vidéo ne porte ni cours ni chorégraphie.
    assert "cours_id" not in lue and "choregraphie_id" not in lue

    modifiee = client.put(f"/videos/{video.id}", json={"nom": "Prise 2", "description": None}).json()
    assert (modifiee["nom"], modifiee["description"]) == ("Prise 2", None)
    assert client.delete(f"/videos/{video.id}").status_code == 204
    assert client.get(f"/videos/{video.id}").status_code == 404


def test_supprimer_video_efface_le_fichier_et_la_vignette(client, db_session):
    ecole, admin = _setup(db_session)
    fichier = dossier_ecole(ecole.id) / "a-supprimer.mp4"
    vignette = dossier_ecole(ecole.id) / "a-supprimer.jpg"
    fichier.write_bytes(b"x")
    vignette.write_bytes(b"x")
    video = _video(
        db_session, ecole, admin,
        lien_fichier=chemin_relatif(ecole.id, fichier.name), poster=chemin_relatif(ecole.id, vignette.name),
    )
    assert client.delete(f"/videos/{video.id}").status_code == 204
    assert not fichier.exists() and not vignette.exists()


def test_le_metier_est_prevenu_d_une_suppression(db_session):
    """`quand_supprimee` : ce qui rattache des vidéos à ses objets défait
    ses liens lui-même (voir choregraphies.py)."""
    from videos import Videos

    ecole, admin = _setup(db_session)
    videos = Videos()
    prevenus = []
    videos.quand_supprimee(lambda db, video_id: prevenus.append(video_id))
    video = videos.create(db_session, ecole_id=ecole.id, nom="V", lien_fichier="", uploaded_by=admin.id)
    video_id = video.id
    assert videos.delete(db_session, video_id) is True
    assert prevenus == [video_id]


def test_usage_ecole(client, db_session):
    """Panneau "Usage vidéo" (Admin > École) : octets utilisés, secondes de
    vidéo, top 10 par taille décroissante. Deux vrais fichiers écrits sur
    le disque (taille lue à la demande, pas stockée) + une vidéo sans
    fichier (ignorée) + une vidéo dont le fichier est absent du disque
    (ignorée sans erreur) + une vidéo d'une autre école (jamais comptée)."""
    ecole, admin = _setup(db_session)
    autre = Ecoles().create(db_session, nom="Autre", code_postal="11111")
    admin_autre = Comptes().create(db_session, ecole_id=autre.id, role="admin", nom="X", prenom="Y")

    petit = dossier_ecole(ecole.id) / "petit.mp4"
    grand = dossier_ecole(ecole.id) / "grand.mp4"
    ailleurs = dossier_ecole(autre.id) / "ailleurs.mp4"
    petit.write_bytes(b"x" * 1000)
    grand.write_bytes(b"x" * 5000)
    ailleurs.write_bytes(b"x" * 9000)
    try:
        _video(db_session, ecole, admin, nom="Petit", lien_fichier=chemin_relatif(ecole.id, "petit.mp4"), duree_secondes=10)
        _video(db_session, ecole, admin, nom="Grand", lien_fichier=chemin_relatif(ecole.id, "grand.mp4"), duree_secondes=50)
        _video(db_session, ecole, admin, nom="Sans fichier")
        _video(db_session, ecole, admin, nom="Fichier absent", lien_fichier=chemin_relatif(ecole.id, "absent.mp4"))
        _video(db_session, autre, admin_autre, nom="Ailleurs", lien_fichier=chemin_relatif(autre.id, "ailleurs.mp4"))

        usage = client.get(f"/ecoles/{ecole.id}/videos/usage").json()
        assert usage["total_octets"] == usage["total_toutes_saisons_octets"] == 6000
        assert usage["total_secondes"] == 60
        assert [(v["titre"], v["taille_octets"]) for v in usage["top_videos"]] == [("Grand", 5000), ("Petit", 1000)]
    finally:
        for fichier in (petit, grand, ailleurs):
            fichier.unlink(missing_ok=True)


def test_usage_ecole_sans_video(client, db_session):
    ecole, _ = _setup(db_session)
    usage = client.get(f"/ecoles/{ecole.id}/videos/usage").json()
    assert usage == {
        "total_octets": 0, "total_secondes": 0, "total_toutes_saisons_octets": 0,
        "total_toutes_saisons_secondes": 0, "top_videos": [],
    }


# --- Envoi par blocs ---


def test_upload_par_blocs_puis_video(client, db_session):
    """Tous les blocs arrivent, puis l'envoi devient une vidéo (voir
    videos.py : Televersement, finaliser)."""
    ecole, admin = _setup(db_session)
    contenu = _FICHIER_DEMO.read_bytes()

    ouverture = _ouvrir(client, ecole, len(contenu))
    assert ouverture.status_code == 201
    upload_id = ouverture.json()["id"]

    moitie = len(contenu) // 2
    r1 = _ecrire_bloc(client, upload_id, 0, contenu[:moitie])
    assert r1.json() == {
        "id": upload_id, "octets_recus": moitie, "octets_total": len(contenu), "complet": False
    }
    assert _ecrire_bloc(client, upload_id, moitie, contenu[moitie:]).json()["complet"] is True

    video = videos_client.finaliser(db_session, upload_id, nom="Upload test", uploaded_by=admin.id, description="Une description")
    try:
        assert (video.nom, video.ecole_id, video.statut) == ("Upload test", ecole.id, "complete")
        # Vraie durée mesurée (voir duree.py).
        assert video.duree_secondes == 22
        assert (DOSSIER_VIDEOS_LIVE / video.lien_fichier).exists()
        assert video.poster is not None and (DOSSIER_VIDEOS_LIVE / video.poster).exists()
        # La session reste, inerte : elle rend `finaliser` idempotent.
        assert client.get(f"/videos/televersements/{upload_id}").json()["complet"] is True
        assert videos_client.finaliser(db_session, upload_id, nom="Encore", uploaded_by=admin.id).id == video.id
    finally:
        (DOSSIER_VIDEOS_LIVE / video.lien_fichier).unlink(missing_ok=True)
        if video.poster:
            (DOSSIER_VIDEOS_LIVE / video.poster).unlink(missing_ok=True)


def test_video_creee_avant_la_fin_de_l_envoi(client, db_session):
    """« Ajouter » cliqué pendant l'envoi : la vidéo existe tout de suite
    ('en_cours'), le dernier bloc la termine."""
    ecole, admin = _setup(db_session)
    contenu = _FICHIER_DEMO.read_bytes()
    upload_id = _ouvrir(client, ecole, len(contenu)).json()["id"]
    moitie = len(contenu) // 2
    _ecrire_bloc(client, upload_id, 0, contenu[:moitie])

    video = videos_client.finaliser(db_session, upload_id, nom="En cours", uploaded_by=admin.id)
    assert (video.statut, video.lien_fichier) == ("en_cours", "")

    _ecrire_bloc(client, upload_id, moitie, contenu[moitie:])
    finie = client.get(f"/videos/{video.id}").json()
    try:
        assert finie["statut"] == "complete" and finie["duree_secondes"] == 22
    finally:
        (DOSSIER_VIDEOS_LIVE / finie["lien_fichier"]).unlink(missing_ok=True)
        if finie["poster"]:
            (DOSSIER_VIDEOS_LIVE / finie["poster"]).unlink(missing_ok=True)


def test_decalage_invalide_renvoie_le_bon_decalage(client, db_session):
    ecole, _ = _setup(db_session)
    upload_id = _ouvrir(client, ecole, 100).json()["id"]
    _ecrire_bloc(client, upload_id, 0, b"x" * 40)
    reponse = _ecrire_bloc(client, upload_id, 10, b"x" * 10)
    assert reponse.status_code == 409
    assert reponse.json()["detail"] == {"octets_recus": 40}
    client.delete(f"/videos/televersements/{upload_id}")


def test_annuler_televersement_nettoie_tout(client, db_session):
    """« Annuler » arrête tout : le fichier partiel, et la vidéo si
    « Ajouter » avait déjà été cliqué."""
    ecole, admin = _setup(db_session)
    upload_id = _ouvrir(client, ecole, 100).json()["id"]
    _ecrire_bloc(client, upload_id, 0, b"x" * 50)
    video_id = videos_client.finaliser(db_session, upload_id, nom="Annulée", uploaded_by=admin.id).id

    assert client.delete(f"/videos/televersements/{upload_id}").status_code == 204
    assert client.get(f"/videos/{video_id}").status_code == 404
    assert client.get(f"/videos/televersements/{upload_id}").status_code == 404


def test_televersement_introuvable(client, db_session):
    assert client.get("/videos/televersements/inconnu").status_code == 404
    assert _ecrire_bloc(client, "inconnu", 0, b"x").status_code == 404
    assert client.delete("/videos/televersements/inconnu").status_code == 404
    assert videos_client.finaliser(db_session, "inconnu", nom="X", uploaded_by=1) is None


# --- Droits (les vraies vérifications) ---


@pytest.mark.rbac_reel
def test_droits_du_module_generique(client, db_session):
    """Lire : toute l'école. Modifier ou supprimer par le seul numéro, et
    l'usage : les admins. Rien pour une autre école."""
    from conftest import entetes_session

    ecole, admin = _setup(db_session)
    eleve = Comptes().create(db_session, ecole_id=ecole.id, role="eleve", nom="Martin", prenom="Zoé")
    autre = Ecoles().create(db_session, nom="Autre", code_postal="11111")
    etranger = Comptes().create(db_session, ecole_id=autre.id, role="admin", nom="X", prenom="Y")
    video = _video(db_session, ecole, admin)

    assert client.get(f"/videos/{video.id}").status_code == 401
    assert client.get(f"/videos/{video.id}", headers=entetes_session(eleve)).status_code == 200
    assert client.get(f"/videos/{video.id}", headers=entetes_session(etranger)).status_code == 403

    assert client.put(f"/videos/{video.id}", json={"nom": "X"}, headers=entetes_session(eleve)).status_code == 403
    assert client.delete(f"/videos/{video.id}", headers=entetes_session(eleve)).status_code == 403
    assert client.delete(f"/videos/{video.id}", headers=entetes_session(etranger)).status_code == 403
    assert client.get(f"/ecoles/{ecole.id}/videos/usage", headers=entetes_session(eleve)).status_code == 403

    # Chacun peut envoyer un fichier dans SON école.
    corps = {"extension": ".mp4", "octets_total": 10}
    assert client.post(f"/ecoles/{ecole.id}/videos/televersements", json=corps, headers=entetes_session(eleve)).status_code == 201
    assert client.post(f"/ecoles/{ecole.id}/videos/televersements", json=corps, headers=entetes_session(etranger)).status_code == 403

    assert client.delete(f"/videos/{video.id}", headers=entetes_session(admin)).status_code == 204
