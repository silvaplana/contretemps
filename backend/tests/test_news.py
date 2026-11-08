"""Tests du module Actualités (spec/modules/actualites.md) : l'ordre des
actus, les brouillons, « Nouveau », la notification après Annuler, l'option
d'ouverture, les droits (`rbac_reel`) et les actions de l'assistant."""

from datetime import date, timedelta

import pytest
from conftest import entetes_session

from app.main import app
from comptes import Comptes, rbac
from ecoles import Ecoles
from groups import rights
from news.models import NewsItem


@pytest.fixture(autouse=True)
def _pas_de_minuteur(monkeypatch):
    """La notification programmée à 10 s ouvrirait la vraie base : dans les
    tests, rien n'est programmé, `send_notification` s'appelle à la main."""
    from app.main import core

    monkeypatch.setattr(core.news_client, "session_factory", None)


@pytest.fixture()
def e(db_session):
    comptes = Comptes()
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    autre = Ecoles().create(db_session, nom="Fight Lab", code_postal="13600")
    seb = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Richard", prenom="Seb")
    rights.add(db_session, seb, "news.publish")
    # Pendant le test, Zoé fait partie des élèves qui voient les actus.
    zoe = comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="Martin", prenom="Zoé")
    rights.add(db_session, zoe, "news.read")
    db_session.commit()
    return {
        "ecole": ecole,
        "autre": autre,
        "seb": seb,
        "admin": comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia"),
        "zoe": zoe,
        "voisin": comptes.create(db_session, ecole_id=autre.id, role="eleve", nom="Roux", prenom="Ana"),
    }


@pytest.fixture()
def en_tant_que():
    def choisir(compte):
        app.dependency_overrides[rbac.compte_appelant] = lambda: compte

    yield choisir
    app.dependency_overrides[rbac.compte_appelant] = lambda: None


def _publier(client, ecole_id, body, **kw):
    reponse = client.post(f"/ecoles/{ecole_id}/news", json={"body": body, **kw})
    assert reponse.status_code == 201, reponse.text
    return reponse.json()


def test_ordre_important_en_haut_puis_le_plus_recent(client, db_session, e):
    eid = e["ecole"].id
    demain = (date.today() + timedelta(days=1)).isoformat()
    hier = (date.today() - timedelta(days=1)).isoformat()
    _publier(client, eid, "Pas de cours le 11", level="important", on_top_until=demain)
    _publier(client, eid, "Gala le 13 juin")
    _publier(client, eid, "Ancienne alerte", level="important", on_top_until=hier)
    _publier(client, eid, "Salle 2 jeudi", level="brief", on_top_until=demain)
    _publier(client, eid, "Brouillon caché", publish=False)
    _publier(client, e["autre"].id, "Chez les voisins")

    fil = client.get(f"/ecoles/{eid}/news").json()
    assert [i["body"] for i in fil["items"]] == ["Pas de cours le 11", "Salle 2 jeudi", "Ancienne alerte", "Gala le 13 juin"]
    assert [i["on_top"] for i in fil["items"]] == [True, False, False, False]
    # Une brève n'a pas de date « en haut jusqu'au ».
    assert fil["items"][1]["on_top_until"] is None
    assert [i["body"] for i in client.get(f"/ecoles/{eid}/news/atelier").json()][0] == "Brouillon caché"


def test_brouillon_publie_puis_annule(client, e):
    eid = e["ecole"].id
    actu = _publier(client, eid, "Stage de salsa", publish=False)
    assert actu["published_at"] is None
    url = f"/ecoles/{eid}/news/{actu['id']}"
    publiee = client.put(url, json={"body": "Stage de salsa le 23", "publish": True}).json()
    assert publiee["published_at"] and publiee["body"] == "Stage de salsa le 23"
    # Enregistrer une actu publiée garde sa date de publication.
    assert client.put(url, json={"body": "Stage le 23", "publish": True}).json()["published_at"] == publiee["published_at"]
    assert client.post(f"{url}/unpublish").json()["published_at"] is None
    assert client.get(f"/ecoles/{eid}/news").json()["items"] == []
    assert client.delete(url).status_code == 204
    assert client.get(f"/ecoles/{eid}/news/atelier").json() == []
    # Une actu d'une autre école reste introuvable.
    voisine = _publier(client, e["autre"].id, "Chez les voisins")
    assert client.delete(f"/ecoles/{eid}/news/{voisine['id']}").status_code == 404


def test_nouveau_jusqu_a_la_visite_suivante(client, e, en_tant_que):
    eid = e["ecole"].id
    en_tant_que(e["zoe"])
    assert client.get(f"/ecoles/{eid}/news").json()["items"] == []  # première visite
    en_tant_que(e["seb"])
    _publier(client, eid, "Gala le 13 juin")
    assert client.get(f"/ecoles/{eid}/news").json()["items"][0]["is_new"] is False  # sa propre actu
    en_tant_que(e["zoe"])
    assert client.get(f"/ecoles/{eid}/news").json()["items"][0]["is_new"] is True
    assert client.get(f"/ecoles/{eid}/news").json()["items"][0]["is_new"] is False


class FauxNotifications:
    def __init__(self):
        self.envois = []

    def envoyer_a_compte(self, db, compte_id, titre, corps):
        self.envois.append((compte_id, titre, corps))


def test_notification_a_qui_voit_les_actus_sauf_l_auteur_et_pas_apres_annuler(client, db_session, e, en_tant_que, monkeypatch):
    from app.main import core

    faux = FauxNotifications()
    monkeypatch.setattr(core.news_client, "notifications", faux)
    eid = e["ecole"].id
    en_tant_que(e["seb"])
    long = "Pas de cours mardi 11 novembre. " * 10
    actu = _publier(client, eid, long, level="important", notify=True)
    # Julia (admin sans le droit « Voir les actualités ») ne la reçoit pas.
    assert core.news_client.send_notification(db_session, actu["id"]) == 1
    assert {c for c, _, _ in faux.envois} == {e["zoe"].id}
    _, titre, corps = faux.envois[0]
    assert titre == "Contretemps" and len(corps) == 100 and corps.endswith("…")
    # Une seule fois.
    assert core.news_client.send_notification(db_session, actu["id"]) == 0

    # Annuler pendant les 10 s : repasse en brouillon, rien ne part.
    annulee = _publier(client, eid, "Oups", notify=True)
    client.post(f"/ecoles/{eid}/news/{annulee['id']}/unpublish")
    db_session.expire_all()
    assert core.news_client.send_notification(db_session, annulee["id"]) == 0
    # Sans l'interrupteur, rien non plus.
    muette = _publier(client, eid, "Brève sans bruit", level="brief")
    assert core.news_client.send_notification(db_session, muette["id"]) == 0


def test_option_ouvrir_sur_les_actus(client, e):
    url = f"/ecoles/{e['ecole'].id}/news/settings"
    assert client.get(url).json() == {"open_on_news": True, "can_read": True, "can_choose_readers": True}
    assert client.put(url, json={"open_on_news": False}).json() == {"open_on_news": False, "can_read": True, "can_choose_readers": True}
    assert client.get(url).json() == {"open_on_news": False, "can_read": True, "can_choose_readers": True}
    assert client.get(f"/ecoles/{e['autre'].id}/news/settings").json() == {"open_on_news": True, "can_read": True, "can_choose_readers": True}


@pytest.mark.rbac_reel
def test_droits(client, db_session, e):
    eid = e["ecole"].id
    seb, admin, zoe, voisin = (entetes_session(e[k]) for k in ("seb", "admin", "zoe", "voisin"))
    actu = client.post(f"/ecoles/{eid}/news", json={"body": "Gala"}, headers=seb)
    assert actu.status_code == 201, actu.text
    assert actu.json()["author_name"] == "Seb"
    # Pendant le test, lit qui a « Voir les actualités » ou « Publier les
    # actualités » ; seul le second écrit (un admin sans la coche non plus).
    fil = client.get(f"/ecoles/{eid}/news", headers=zoe).json()
    assert len(fil["items"]) == 1 and fil["can_publish"] is False
    assert client.get(f"/ecoles/{eid}/news", headers=seb).json()["can_publish"] is True
    for entetes in (zoe, admin):
        assert client.post(f"/ecoles/{eid}/news", json={"body": "x"}, headers=entetes).status_code == 403
        assert client.get(f"/ecoles/{eid}/news/atelier", headers=entetes).status_code == 403
        assert client.put(f"/ecoles/{eid}/news/settings", json={"open_on_news": False}, headers=entetes).status_code == 403
    assert client.get(f"/ecoles/{eid}/news/settings", headers=zoe).json() == {"open_on_news": True, "can_read": True, "can_choose_readers": False}
    # Sans le droit : pas d'onglet, pas d'actus, l'appli ne s'ouvre pas dessus.
    assert client.get(f"/ecoles/{eid}/news/settings", headers=admin).json() == {"open_on_news": False, "can_read": False, "can_choose_readers": False}
    assert client.get(f"/ecoles/{eid}/news", headers=admin).status_code == 403
    # Une autre école ne lit rien.
    assert client.get(f"/ecoles/{eid}/news", headers=voisin).status_code == 403
    assert db_session.query(NewsItem).count() == 1


def test_actions_de_l_assistant(db_session, e):
    from app.main import core
    from assistant.modifications import Refus
    from news.actions import actions

    par_nom = {a.name: a for a in actions(core.news_client)}
    publier = par_nom["publish_news"]
    ligne = publier.prepare(db_session, e["seb"], e["ecole"].id, publier.params(body="Pas de cours le 11", level="important"))
    assert ligne.libelle == "Publier l'actu importante « Pas de cours le 11 », avec notification"
    ligne.faire(db_session)
    actu = db_session.query(NewsItem).one()
    assert actu.published_at and actu.on_top_until == date.today() + timedelta(days=7) and actu.notify
    with pytest.raises(Refus):
        publier.prepare(db_session, e["zoe"], e["ecole"].id, publier.params(body="x"))
    supprimer = par_nom["delete_news"]
    with pytest.raises(Refus):
        supprimer.prepare(db_session, e["seb"], e["autre"].id, supprimer.params(news_id=actu.id))
    supprimer.prepare(db_session, e["seb"], e["ecole"].id, supprimer.params(news_id=actu.id)).faire(db_session)
    assert db_session.query(NewsItem).count() == 0


# --- Étape 2 : photo, vidéo, document ---


@pytest.fixture()
def photos(tmp_path, monkeypatch):
    from app.main import core
    from news.storage import PHOTO_MAX_BYTES
    from storage import LocalStorage

    monkeypatch.setattr(core.news_client, "storage", LocalStorage(tmp_path, PHOTO_MAX_BYTES))
    return core.news_client.storage


def _image():
    import io

    from PIL import Image

    tampon = io.BytesIO()
    Image.new("RGB", (2400, 1200), (200, 40, 40)).save(tampon, "PNG")
    return tampon.getvalue()


def _envoyer_photo(client, ecole_id):
    reponse = client.post(f"/ecoles/{ecole_id}/news/photos", files={"fichier": ("gala.png", _image(), "image/png")})
    assert reponse.status_code == 201, reponse.text
    return reponse.json()["photo"]


def test_photo_envoyee_montree_puis_effacee(client, db_session, e, photos):
    eid = e["ecole"].id
    assert client.post(f"/ecoles/{eid}/news/photos", files={"fichier": ("x.txt", b"pas une image", "text/plain")}).status_code == 400
    sha = _envoyer_photo(client, eid)
    actu = _publier(client, eid, "Le gala", photo=sha)
    assert actu["photo"] == sha

    image = client.get(f"/ecoles/{eid}/news/{actu['id']}/photo")
    assert image.status_code == 200 and image.headers["content-type"] == "image/jpeg"
    from PIL import Image
    import io

    assert max(Image.open(io.BytesIO(image.content)).size) == 1600
    # La photo d'une autre école ne se montre pas.
    assert client.get(f"/ecoles/{e['autre'].id}/news/{actu['id']}/photo").status_code == 404
    # Une photo inconnue est refusée.
    assert client.post(f"/ecoles/{eid}/news", json={"body": "x", "photo": "0" * 64}).status_code == 400

    # Retirée : elle est effacée du disque.
    client.put(f"/ecoles/{eid}/news/{actu['id']}", json={"body": "Le gala", "photo": None})
    assert not photos.path(eid, sha).exists()

    sha = _envoyer_photo(client, eid)
    actu = _publier(client, eid, "Encore", photo=sha)
    assert client.delete(f"/ecoles/{eid}/news/{actu['id']}").status_code == 204
    assert not photos.path(eid, sha).exists()


def test_video_et_document(client, db_session, e, photos):
    from app.main import core
    from documents.models import DocNode
    from videos.models import Video

    eid = e["ecole"].id
    video = core.videos_client.create(db_session, eid, "Actualité", "x.mp4", e["seb"].id)
    autre_video = core.videos_client.create(db_session, e["autre"].id, "Voisins", "y.mp4", e["voisin"].id)
    fichier = DocNode(org_id=eid, space="public", kind="file", name="Planning.pdf")
    dossier = DocNode(org_id=eid, space="public", kind="folder", name="AG")
    chez_voisin = DocNode(org_id=e["autre"].id, space="public", kind="file", name="Leur.pdf")
    db_session.add_all([fichier, dossier, chez_voisin])
    db_session.commit()

    actu = _publier(client, eid, "Le stage en vidéo", video_id=video.id, document_id=fichier.id)
    assert actu["video"]["id"] == video.id
    assert actu["document"] == {"id": fichier.id, "name": "Planning.pdf"}
    assert client.get(f"/ecoles/{eid}/news").json()["items"][0]["video"]["id"] == video.id

    for mauvais in ({"video_id": autre_video.id}, {"document_id": dossier.id}, {"document_id": chez_voisin.id},
                    {"video_id": video.id, "photo": _envoyer_photo(client, eid)}):
        assert client.post(f"/ecoles/{eid}/news", json={"body": "x", **mauvais}).status_code == 400, mauvais

    # Une brève n'a pas de média : passer en brève efface la vidéo.
    video_id = video.id
    breve = client.put(f"/ecoles/{eid}/news/{actu['id']}", json={"body": "Court", "level": "brief", "video_id": video_id}).json()
    assert breve["video"] is None and breve["document"] is None
    db_session.expire_all()
    assert db_session.get(Video, video_id) is None

    # Une vidéo supprimée ailleurs (panneau Usage) laisse l'actu.
    video = core.videos_client.create(db_session, eid, "Actualité", "z.mp4", e["seb"].id)
    actu = _publier(client, eid, "Avec vidéo", video_id=video.id)
    core.videos_client.delete(db_session, actu["video"]["id"])
    db_session.expire_all()
    assert db_session.get(NewsItem, actu["id"]).video_id is None


@pytest.mark.rbac_reel
def test_qui_voit_les_actus_pendant_le_test(client, db_session, e):
    """L'administrateur principal coche, dans l'Atelier, qui voit les actus."""
    eid = e["ecole"].id
    patron = Comptes().create(db_session, ecole_id=eid, role="admin", nom="Chef", prenom="Anne")
    Comptes().ajouter_role(db_session, patron, "owner")
    rights.add(db_session, patron, "news.publish")
    db_session.commit()
    chef, admin = (entetes_session(c) for c in (patron, e["admin"]))
    url = f"/ecoles/{eid}/news/readers"

    assert client.get(f"/ecoles/{eid}/news/settings", headers=chef).json()["can_choose_readers"] is True
    # Julia est admin, pas administratrice principale.
    assert client.get(f"/ecoles/{eid}/news/settings", headers=admin).json()["can_choose_readers"] is False
    assert client.get(url, headers=admin).status_code == 403

    lecteurs = {r["name"]: r for r in client.get(url, headers=chef).json()}
    assert "Ana Roux" not in lecteurs  # une autre école
    assert lecteurs["Zoé Martin"]["reads"] is True and lecteurs["Julia Dho"]["reads"] is False
    assert lecteurs["Seb Richard"]["publishes"] is True

    assert client.get(f"/ecoles/{eid}/news", headers=admin).status_code == 403
    assert client.put(f"{url}/{e['admin'].id}", json={"reads": True}, headers=chef).json()["reads"] is True
    assert client.get(f"/ecoles/{eid}/news", headers=admin).status_code == 200
    assert client.put(f"{url}/{e['admin'].id}", json={"reads": False}, headers=chef).json()["reads"] is False
    assert client.get(f"/ecoles/{eid}/news", headers=admin).status_code == 403
    assert client.put(f"{url}/{e['voisin'].id}", json={"reads": True}, headers=chef).status_code == 404
