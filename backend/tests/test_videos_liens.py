"""Vidéos protégées (documents-phase-contretemps.md, étape 1) : le fichier
n'est plus servi en accès libre (/media/videos), seulement par un lien
signé à durée limitée remis à qui peut voir la vidéo."""

import time
from urllib.parse import parse_qs, urlsplit

import pytest
from app.main import videos_client
from comptes import Comptes
from conftest import entetes_session
from ecoles import Ecoles
from securite import liens
from videos import chemin_relatif, dossier_ecole

pytestmark = pytest.mark.rbac_reel

CONTENU = bytes(range(256)) * 40


@pytest.fixture()
def video(db_session):
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    admin = Comptes().create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia")
    voisine = Ecoles().create(db_session, nom="Voisine", code_postal="83000")
    voisin = Comptes().create(db_session, ecole_id=voisine.id, role="admin", nom="Z", prenom="W")
    fichier = dossier_ecole(ecole.id) / "protegee.mp4"
    poster = dossier_ecole(ecole.id) / "protegee.jpg"
    fichier.write_bytes(CONTENU)
    poster.write_bytes(b"jpeg")
    v = videos_client.create(
        db_session, ecole_id=ecole.id, uploaded_by=admin.id, nom="Prise 1",
        lien_fichier=chemin_relatif(ecole.id, fichier.name), poster=chemin_relatif(ecole.id, poster.name),
    )
    yield {"video": v, "admin": admin, "voisin": voisin}
    fichier.unlink(missing_ok=True)
    poster.unlink(missing_ok=True)


def test_le_lien_signe_donne_la_video_et_son_apercu(client, video):
    lue = client.get(f"/videos/{video['video'].id}", headers=entetes_session(video["admin"])).json()
    assert lue["url"].startswith(f"/videos/{video['video'].id}/fichier?")
    # Lu par la balise <video> : sans session.
    reponse = client.get(lue["url"])
    assert reponse.status_code == 200 and reponse.content == CONTENU
    # Lecture progressive : le navigateur demande des morceaux.
    morceau = client.get(lue["url"], headers={"Range": "bytes=100-199"})
    assert morceau.status_code == 206 and morceau.content == CONTENU[100:200]
    assert client.get(lue["poster_url"]).content == b"jpeg"


def test_sans_lien_signe_rien(client, video):
    v = video["video"]
    assert client.get(f"/media/videos/{v.lien_fichier}").status_code == 404
    assert client.get(f"/videos/{v.id}/fichier").status_code == 403
    lue = client.get(f"/videos/{v.id}", headers=entetes_session(video["admin"])).json()
    params = parse_qs(urlsplit(lue["url"]).query)
    # Signature d'une autre vidéo, ou du fichier pour l'aperçu : refusé.
    assert client.get(f"/videos/{v.id + 1}/fichier?e={params['e'][0]}&s={params['s'][0]}").status_code == 403
    assert client.get(f"/videos/{v.id}/poster?e={params['e'][0]}&s={params['s'][0]}").status_code == 403
    # Date d'expiration rallongée à la main : la signature ne correspond plus.
    plus_tard = int(params["e"][0]) + 86400
    assert client.get(f"/videos/{v.id}/fichier?e={plus_tard}&s={params['s'][0]}").status_code == 403


def test_le_lien_expire(client, video):
    v = video["video"]
    vieux = liens.parametres(f"video:{v.id}:fichier", maintenant=time.time() - 2 * 86400)
    assert client.get(f"/videos/{v.id}/fichier?{vieux}").status_code == 403


def test_une_autre_ecole_n_obtient_pas_de_lien(client, video):
    reponse = client.get(f"/videos/{video['video'].id}", headers=entetes_session(video["voisin"]))
    assert reponse.status_code == 403
