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
    zoe = comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="Martin", prenom="Zoé")
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
    # Tout le monde la reçoit, sauf Seb qui l'a écrite.
    assert core.news_client.send_notification(db_session, actu["id"]) == 2
    assert {c for c, _, _ in faux.envois} == {e["zoe"].id, e["admin"].id}
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
    assert client.get(url).json() == {"open_on_news": True, "media_first": False, "can_read": True, "visible_to_all": True, "instagram_hashtag": "", "instagram_publish": True, "has_news": False}
    assert client.put(url, json={"open_on_news": False}).json() == {"open_on_news": False, "media_first": False, "can_read": True, "visible_to_all": True, "instagram_hashtag": "", "instagram_publish": True, "has_news": False}
    assert client.get(url).json() == {"open_on_news": False, "media_first": False, "can_read": True, "visible_to_all": True, "instagram_hashtag": "", "instagram_publish": True, "has_news": False}
    assert client.get(f"/ecoles/{e['autre'].id}/news/settings").json() == {"open_on_news": True, "media_first": False, "can_read": True, "visible_to_all": True, "instagram_hashtag": "", "instagram_publish": True, "has_news": False}


def test_pas_d_ouverture_sur_les_actus_tant_qu_il_n_y_en_a_aucune(client, e):
    # Seb, 10 novembre : zéro actu, l'appli s'ouvre comme d'habitude.
    eid = e["ecole"].id
    url = f"/ecoles/{eid}/news/settings"
    assert client.get(url).json()["has_news"] is False
    client.post(f"/ecoles/{eid}/news", json={"body": "Brouillon", "publish": False})
    assert client.get(url).json()["has_news"] is False
    _publier(client, eid, "Reprise des cours")
    assert client.get(url).json()["has_news"] is True
    assert client.get(f"/ecoles/{e['autre'].id}/news/settings").json()["has_news"] is False


def test_en_haut_de_chaque_actu(client, e):
    """« En haut de chaque actu : Texte | Photo, vidéo » (Seb, 9 novembre) :
    un réglage de l'école, que le fil donne à tout le monde."""
    eid = e["ecole"].id
    url = f"/ecoles/{eid}/news/settings"
    assert client.get(f"/ecoles/{eid}/news").json()["media_first"] is False
    reglages = client.put(url, json={"media_first": True}).json()
    # Seul ce qui est donné change.
    assert reglages["media_first"] is True and reglages["open_on_news"] is True
    assert client.get(f"/ecoles/{eid}/news").json()["media_first"] is True
    assert client.get(f"/ecoles/{e['autre'].id}/news").json()["media_first"] is False


@pytest.mark.rbac_reel
def test_droits(client, db_session, e):
    eid = e["ecole"].id
    seb, admin, zoe, voisin = (entetes_session(e[k]) for k in ("seb", "admin", "zoe", "voisin"))
    actu = client.post(f"/ecoles/{eid}/news", json={"body": "Gala"}, headers=seb)
    assert actu.status_code == 201, actu.text
    assert actu.json()["author_name"] == "Seb"
    # Tout le monde lit ; seul « Publier les actualités » écrit (un admin
    # sans la coche non plus).
    fil = client.get(f"/ecoles/{eid}/news", headers=zoe).json()
    assert len(fil["items"]) == 1 and fil["can_publish"] is False
    assert client.get(f"/ecoles/{eid}/news", headers=seb).json()["can_publish"] is True
    for entetes in (zoe, admin):
        assert client.post(f"/ecoles/{eid}/news", json={"body": "x"}, headers=entetes).status_code == 403
        assert client.get(f"/ecoles/{eid}/news/atelier", headers=entetes).status_code == 403
        assert client.put(f"/ecoles/{eid}/news/settings", json={"open_on_news": False}, headers=entetes).status_code == 403
        assert client.put(f"/ecoles/{eid}/news/settings", json={"visible_to_all": False}, headers=entetes).status_code == 403
    assert client.get(f"/ecoles/{eid}/news/settings", headers=zoe).json() == {"open_on_news": True, "media_first": False, "can_read": True, "visible_to_all": True, "instagram_hashtag": "", "instagram_publish": True, "has_news": True}
    assert client.get(f"/ecoles/{eid}/news", headers=admin).status_code == 200
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


def _image(couleur=(200, 40, 40)):
    import io

    from PIL import Image

    tampon = io.BytesIO()
    Image.new("RGB", (2400, 1200), couleur).save(tampon, "PNG")
    return tampon.getvalue()


def _envoyer_photo(client, ecole_id, couleur=(200, 40, 40)):
    reponse = client.post(f"/ecoles/{ecole_id}/news/photos", files={"fichier": ("gala.png", _image(couleur), "image/png")})
    assert reponse.status_code == 201, reponse.text
    return reponse.json()["photo"]


def test_carrousel_de_photos_montrees_puis_effacees(client, db_session, e, photos):
    eid = e["ecole"].id
    assert client.post(f"/ecoles/{eid}/news/photos", files={"fichier": ("x.txt", b"pas une image", "text/plain")}).status_code == 400
    rouge, bleue = _envoyer_photo(client, eid), _envoyer_photo(client, eid, (20, 40, 200))
    actu = _publier(client, eid, "Le gala", media=[{"photo": rouge}, {"photo": bleue}])
    assert actu["media"] == [{"photo": rouge, "video": None, "link": None, "title": None},
                             {"photo": bleue, "video": None, "link": None, "title": None}]

    image = client.get(f"/ecoles/{eid}/news/{actu['id']}/photos/{bleue}")
    assert image.status_code == 200 and image.headers["content-type"] == "image/jpeg"
    from PIL import Image
    import io

    assert max(Image.open(io.BytesIO(image.content)).size) == 1600
    # La photo d'une autre école, ou d'une autre actu, ne se montre pas.
    assert client.get(f"/ecoles/{e['autre'].id}/news/{actu['id']}/photos/{bleue}").status_code == 404
    autre = _publier(client, eid, "Autre")
    assert client.get(f"/ecoles/{eid}/news/{autre['id']}/photos/{bleue}").status_code == 404
    # Une photo inconnue est refusée ; 10 éléments au plus.
    assert client.post(f"/ecoles/{eid}/news", json={"body": "x", "media": [{"photo": "0" * 64}]}).status_code == 400
    assert client.post(f"/ecoles/{eid}/news", json={"body": "x", "media": [{"photo": rouge}] * 11}).status_code == 422

    # L'ordre change ; la photo retirée est effacée du disque, l'autre reste.
    remise = client.put(f"/ecoles/{eid}/news/{actu['id']}", json={"body": "Le gala", "media": [{"photo": bleue}]}).json()
    assert [m["photo"] for m in remise["media"]] == [bleue]
    assert not photos.path(eid, rouge).exists() and photos.path(eid, bleue).exists()

    assert client.delete(f"/ecoles/{eid}/news/{actu['id']}").status_code == 204
    assert not photos.path(eid, bleue).exists()


def test_liens_youtube_et_site_dans_le_carrousel(client, db_session, e, photos, monkeypatch):
    from news import links

    lus = []

    def lire(url):
        lus.append(url)
        if url.startswith("https://ferme"):
            raise links.LinkError("Ce lien ne répond pas")
        return links.Preview(title="Le gala 2026", image=_image((20, 160, 60)) if "youtu" in url else None)

    monkeypatch.setattr(links, "read", lire)
    eid = e["ecole"].id
    youtube = client.post(f"/ecoles/{eid}/news/links", json={"url": " https://youtu.be/dQw4w9WgXcQ "})
    assert youtube.status_code == 201, youtube.text
    youtube = youtube.json()
    assert youtube["link"] == "https://youtu.be/dQw4w9WgXcQ" and youtube["title"] == "Le gala 2026"
    assert youtube["photo"] and youtube["preview"].startswith("data:image/jpeg;base64,")
    site = client.post(f"/ecoles/{eid}/news/links", json={"url": "https://contretemps.fr/gala"}).json()
    assert site["photo"] is None and site["preview"] is None
    assert client.post(f"/ecoles/{eid}/news/links", json={"url": "https://ferme.fr"}).json()["detail"] == "Ce lien ne répond pas"

    photo = _envoyer_photo(client, eid)
    actu = _publier(client, eid, "Le gala", media=[
        {"photo": photo},
        {"link": youtube["link"], "title": youtube["title"], "photo": youtube["photo"]},
        {"link": site["link"], "title": site["title"]},
    ])
    assert actu["media"][1:] == [
        {"photo": youtube["photo"], "video": None, "link": "https://youtu.be/dQw4w9WgXcQ", "title": "Le gala 2026"},
        {"photo": None, "video": None, "link": "https://contretemps.fr/gala", "title": "Le gala 2026"},
    ]
    # L'image du site se lit comme une photo de l'actu.
    assert client.get(f"/ecoles/{eid}/news/{actu['id']}/photos/{youtube['photo']}").status_code == 200
    # Pas de lien qui ne soit pas web, ni de lien avec une vidéo.
    for faux in ({"link": "javascript:alert(1)"}, {"link": "https://x.fr", "video_id": 1}):
        assert client.post(f"/ecoles/{eid}/news", json={"body": "x", "media": [faux]}).status_code == 400
    # Le lien retiré, son image est effacée.
    client.put(f"/ecoles/{eid}/news/{actu['id']}", json={"body": "Le gala", "media": [{"photo": photo}]})
    assert not photos.path(eid, youtube["photo"]).exists() and photos.path(eid, photo).exists()


def test_lecture_d_un_lien(monkeypatch):
    from news import links

    for url in ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "https://youtube.com/watch?feature=x&v=dQw4w9WgXcQ",
                "https://youtu.be/dQw4w9WgXcQ?si=abc", "https://m.youtube.com/shorts/dQw4w9WgXcQ"):
        assert links.youtube_id(url) == "dQw4w9WgXcQ", url
    assert links.youtube_id("https://vimeo.com/123") is None
    # Le serveur ne va lire que des adresses publiques.
    for url in ("http://127.0.0.1:8000/docs", "http://localhost/", "http://10.0.0.5/", "file:///etc/passwd"):
        with pytest.raises(links.LinkError):
            links.read(url)
    page = b"""<html><head><title>Ignored</title>
      <meta property="og:title" content="Stage d&#39;hiver" />
      <meta content="/images/stage.jpg" property="og:image"></head></html>"""
    monkeypatch.setattr(links, "_fetch", lambda url, max_bytes: (page, "https://site.fr/stage") if max_bytes == links.PAGE_MAX_BYTES else (b"jpeg", url))
    lu = links.read("https://site.fr/stage")
    assert lu == links.Preview(title="Stage d'hiver", image=b"jpeg")


def test_photo_sans_texte(client, db_session, e, photos, monkeypatch):
    # Seb, 10 novembre : une actu peut n'être qu'une photo ; sans rien, non.
    from app.main import core

    faux = FauxNotifications()
    monkeypatch.setattr(core.news_client, "notifications", faux)
    eid = e["ecole"].id
    photo = _envoyer_photo(client, eid)
    actu = _publier(client, eid, "  ", media=[{"photo": photo}], notify=True)
    assert actu["body"] == "" and len(actu["media"]) == 1
    assert core.news_client.send_notification(db_session, actu["id"]) >= 1
    assert {corps for _, _, corps in faux.envois} == {"Nouvelle actu"}
    for vide in ({"body": ""}, {"body": " ", "level": "brief"}, {"body": "", "level": "brief", "media": [{"photo": photo}]}):
        assert client.post(f"/ecoles/{eid}/news", json=vide).status_code == 400, vide


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

    photo = _envoyer_photo(client, eid)
    actu = _publier(client, eid, "Le stage", media=[{"video_id": video.id}, {"photo": photo}], document_id=fichier.id)
    assert actu["media"][0]["video"]["id"] == video.id and actu["media"][1]["photo"] == photo
    assert actu["document"] == {"id": fichier.id, "name": "Planning.pdf"}
    assert client.get(f"/ecoles/{eid}/news").json()["items"][0]["media"][0]["video"]["id"] == video.id

    for mauvais in ({"media": [{"video_id": autre_video.id}]}, {"document_id": dossier.id}, {"document_id": chez_voisin.id},
                    {"media": [{"video_id": video.id, "photo": photo}]}, {"media": [{}]}):
        assert client.post(f"/ecoles/{eid}/news", json={"body": "x", **mauvais}).status_code == 400, mauvais

    # Une brève n'a pas de média : passer en brève efface la vidéo.
    video_id = video.id
    breve = client.put(f"/ecoles/{eid}/news/{actu['id']}", json={"body": "Court", "level": "brief", "media": [{"video_id": video_id}]}).json()
    assert breve["media"] == [] and breve["document"] is None
    db_session.expire_all()
    assert db_session.get(Video, video_id) is None

    # Une vidéo supprimée ailleurs (panneau Usage) laisse l'actu et ses photos.
    video = core.videos_client.create(db_session, eid, "Actualité", "z.mp4", e["seb"].id)
    photo = _envoyer_photo(client, eid)  # l'autre est partie avec la brève
    actu = _publier(client, eid, "Avec vidéo", media=[{"photo": photo}, {"video_id": video.id}])
    core.videos_client.delete(db_session, video.id)
    db_session.expire_all()
    assert [m["photo"] for m in client.get(f"/ecoles/{eid}/news").json()["items"][0]["media"]] == [photo]


# --- Instagram (§6 bis) ---


@pytest.fixture()
def faux_instagram(monkeypatch):
    """Instagram remplacé : un compte, des posts, des fichiers."""
    from news import instagram

    etat = {"posts": [], "refus": None, "rafraichi": 0}

    def compte(jeton):
        if etat["refus"]:
            raise instagram.InstagramError(etat["refus"])
        return {"user_id": "17841", "username": "contretemps_danse"}

    def posts(jeton):
        if etat["refus"]:
            raise instagram.InstagramError(etat["refus"])
        return etat["posts"]

    def rafraichir(jeton):
        etat["rafraichi"] += 1
        return jeton + "-neuf"

    def telecharger(url, max_bytes):
        return _image() if url.endswith(".jpg") else b"\x00" * 100

    monkeypatch.setattr(instagram, "fetch_account", compte)
    monkeypatch.setattr(instagram, "fetch_recent_media", posts)
    monkeypatch.setattr(instagram, "refresh_token", rafraichir)
    monkeypatch.setattr(instagram, "download", telecharger)
    return etat


def _post(ident, quand, **kw):
    return {"id": ident, "timestamp": quand.strftime("%Y-%m-%dT%H:%M:%S+0000"), "caption": f"Post {ident}", **kw}


def test_instagram_relie_puis_relaie_les_nouveaux_posts(client, db_session, e, en_tant_que, photos, faux_instagram):
    import shutil
    from datetime import datetime, timezone

    from app.main import core
    from news.models import NewsInstagram
    from videos import dossier_ecole

    eid = e["ecole"].id
    url = f"/ecoles/{eid}/news/instagram"
    en_tant_que(e["seb"])
    assert client.get(url).json()["linked"] is False
    faux_instagram["refus"] = "Invalid OAuth access token"
    assert client.put(url, json={"token": "IGAA" + "x" * 40}).status_code == 400
    faux_instagram["refus"] = None
    relie = client.put(url, json={"token": "IGAA" + "x" * 40}).json()
    assert relie["linked"] is True and relie["username"] == "contretemps_danse"

    lien = db_session.get(NewsInstagram, eid)
    assert "IGAA" not in lien.token_encrypted  # la clé est chiffrée
    apres = datetime.now(timezone.utc) + timedelta(minutes=1)
    avant = datetime.now(timezone.utc) - timedelta(days=3)
    faux_instagram["posts"] = [  # du plus récent au plus ancien, comme Instagram
        _post("4", apres + timedelta(minutes=3), media_type="CAROUSEL_ALBUM", children={"data": [
            {"media_type": "IMAGE", "media_url": "https://cdn/a.jpg"},
            {"media_type": "VIDEO", "media_url": "https://cdn/b.mp4"},
        ]}),
        _post("3", apres + timedelta(minutes=2), media_type="VIDEO", media_url="https://cdn/v.mp4"),
        _post("2", apres + timedelta(minutes=1), media_type="IMAGE", media_url="https://cdn/p.jpg"),
        _post("1", avant, media_type="IMAGE", media_url="https://cdn/old.jpg"),  # avant la liaison
    ]
    try:
        assert core.news_instagram.sync_all(db_session) == {eid: 3}
        # Une seule fois.
        assert core.news_instagram.sync(db_session, lien) == 0
        fil = client.get(f"/ecoles/{eid}/news").json()["items"]
        assert [i["body"] for i in fil] == ["Post 4", "Post 3", "Post 2"]
        # Un album arrive entier, dans l'ordre.
        assert [(bool(m["photo"]), bool(m["video"])) for m in fil[0]["media"]] == [(True, False), (False, True)]
        assert fil[1]["media"][0]["video"] and fil[2]["media"][0]["photo"]
        assert {i["author_name"] for i in fil} == {"Seb"} and not any(i["notify"] for i in fil)
        # Une clé refusée plus tard : l'erreur se voit dans les paramètres.
        faux_instagram["refus"] = "Error validating access token"
        core.news_instagram.sync(db_session, lien)
        assert "access token" in client.get(url).json()["last_error"]
    finally:
        shutil.rmtree(dossier_ecole(eid), ignore_errors=True)

    # La clé se renouvelle d'elle-même avant ses 60 jours.
    faux_instagram["refus"] = None
    lien.token_refreshed_at -= timedelta(days=8)
    db_session.commit()
    core.news_instagram.sync(db_session, lien)
    assert faux_instagram["rafraichi"] == 1

    assert client.delete(url).json()["linked"] is False
    assert db_session.get(NewsInstagram, eid) is None


@pytest.mark.rbac_reel
def test_instagram_reserve_a_qui_publie(client, e):
    url = f"/ecoles/{e['ecole'].id}/news/instagram"
    assert client.get(url, headers=entetes_session(e["zoe"])).status_code == 403
    assert client.put(url, json={"token": "x" * 30}, headers=entetes_session(e["admin"])).status_code == 403



@pytest.mark.rbac_reel
def test_actus_visibles_par_tout_le_monde(client, db_session, e, monkeypatch):
    """Fin du test (Seb, 10 novembre) : un interrupteur, dans les Paramètres
    d'édition, remplace le groupe « Voir les actualités ». Éteint, seuls
    ceux qui publient voient les actus."""
    from app.main import core

    eid = e["ecole"].id
    seb, zoe = (entetes_session(e[k]) for k in ("seb", "zoe"))
    url = f"/ecoles/{eid}/news/settings"
    client.post(f"/ecoles/{eid}/news", json={"body": "Gala"}, headers=seb)

    eteint = client.put(url, json={"visible_to_all": False}, headers=seb).json()
    assert eteint["visible_to_all"] is False and eteint["can_read"] is True
    assert client.get(f"/ecoles/{eid}/news", headers=seb).status_code == 200
    assert client.get(f"/ecoles/{eid}/news", headers=zoe).status_code == 403
    assert client.get(url, headers=zoe).json() == {"open_on_news": False, "media_first": False, "can_read": False, "visible_to_all": False, "instagram_hashtag": "", "instagram_publish": True, "has_news": False}
    # L'autre école garde le sien.
    assert client.get(f"/ecoles/{e['autre'].id}/news/settings", headers=entetes_session(e["voisin"])).json()["visible_to_all"] is True

    # Pas de notification à qui ne voit pas les actus.
    faux = FauxNotifications()
    monkeypatch.setattr(core.news_client, "notifications", faux)
    rights.add(db_session, e["admin"], "news.publish")
    db_session.commit()
    actu = client.post(f"/ecoles/{eid}/news", json={"body": "Réunion", "notify": True}, headers=entetes_session(e["admin"])).json()
    assert core.news_client.send_notification(db_session, actu["id"]) == 1
    assert {c for c, _, _ in faux.envois} == {e["seb"].id}

    client.put(url, json={"visible_to_all": True}, headers=seb)
    assert client.get(f"/ecoles/{eid}/news", headers=zoe).status_code == 200


def test_plus_de_droit_voir_les_actualites():
    from news.module import MODULE

    assert [r.key for r in MODULE.rights] == ["news.publish"]


def test_instagram_se_connecter_avec_instagram(client, db_session, e, en_tant_que, faux_instagram, monkeypatch):
    """Le bouton « Se connecter avec Instagram » : Instagram renvoie un code
    sur l'adresse de retour, le serveur l'échange contre une clé et relie."""
    from urllib.parse import parse_qs, urlparse

    from app.main import core
    from news import instagram
    from news.models import NewsInstagram

    eid = e["ecole"].id
    url = f"/ecoles/{eid}/news/instagram"
    en_tant_que(e["seb"])
    # Sans l'appli Meta sur le serveur : pas de bouton, la clé se colle.
    monkeypatch.setattr(core.news_instagram, "app", None)
    assert client.get(url).json()["can_sign_in"] is False
    assert client.post(f"{url}/login").status_code == 409

    monkeypatch.setattr(core.news_instagram, "app", instagram.InstagramApp("123", "secret", "https://x/api/news/instagram/return", "777"))
    echanges = []
    monkeypatch.setattr(instagram, "exchange_code", lambda app, code: echanges.append(code) or "EAA" + "y" * 40)
    monkeypatch.setattr(instagram, "fetch_unified_account", lambda app, jeton: {"id": "1784", "username": "stellina_danse"})
    assert client.get(url).json()["can_sign_in"] is True
    adresse = client.post(f"{url}/login").json()["url"]
    # Connexion unifiée de Meta (Seb, 11 novembre) : la fenêtre de connexion
    # de Facebook, où l'on peut choisir Instagram.
    assert adresse.startswith("https://www.facebook.com/")
    assert "/dialog/oauth?" in adresse
    params = parse_qs(urlparse(adresse).query)
    assert params["client_id"] == ["123"] and params["config_id"] == ["777"]
    assert params["response_type"] == ["code"] and params["override_default_response_type"] == ["true"]
    assert params["redirect_uri"] == ["https://x/api/news/instagram/return"] and "scope" not in params
    state = params["state"][0]

    # Retour de Meta : relié, puis retour sur l'appli de l'école.
    retour = client.get("/news/instagram/return", params={"code": "abc", "state": state}, follow_redirects=False)
    assert retour.status_code == 303 and retour.headers["location"].endswith("/?instagram=ok")
    assert echanges == ["abc"]
    lien = db_session.get(NewsInstagram, eid)
    assert lien is not None and lien.username == "stellina_danse" and lien.linked_by == e["seb"].id
    assert lien.ig_user_id == "1784" and lien.refreshes is False

    # Annulé, ou state fabriqué : rien ne change.
    retour = client.get("/news/instagram/return", params={"error": "access_denied", "state": state}, follow_redirects=False)
    assert retour.headers["location"].endswith("/?instagram=annule")
    retour = client.get("/news/instagram/return", params={"code": "abc", "state": state[:-2] + "xx"}, follow_redirects=False)
    assert retour.headers["location"].endswith("/?instagram=erreur") and echanges == ["abc"]


def test_instagram_connexion_unifiee_relaie_sans_renouveler(client, db_session, e, en_tant_que, photos, faux_instagram, monkeypatch):
    """Un compte relié par la connexion unifiée : ses posts se lisent par son
    identifiant, et sa clé, sans date d'expiration, n'est jamais renouvelée."""
    from datetime import datetime, timedelta, timezone

    from app.main import core
    from news import instagram
    from news.models import NewsInstagram
    from securite.chiffrement import chiffrer

    eid = e["ecole"].id
    lus = []

    def posts_du_compte(app, jeton, ig_user_id):
        lus.append(ig_user_id)
        return faux_instagram["posts"]

    monkeypatch.setattr(instagram, "fetch_account_media", posts_du_compte)
    monkeypatch.setattr(core.news_instagram, "app", instagram.InstagramApp("123", "secret", "https://x/return", "777"))
    il_y_a_un_mois = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30)
    lien = NewsInstagram(org_id=eid, token_encrypted=chiffrer("EAA-suat"), username="stellina_danse",
                         linked_by=e["seb"].id, linked_by_name="Seb", linked_at=il_y_a_un_mois,
                         token_refreshed_at=il_y_a_un_mois, ig_user_id="1784", refreshes=False)
    db_session.add(lien)
    db_session.commit()
    faux_instagram["posts"] = [_post("p1", datetime.now(timezone.utc), media_type="IMAGE", media_url="https://cdn/x.jpg")]
    assert core.news_instagram.sync(db_session, lien) == 1
    assert lus == ["1784"] and faux_instagram["rafraichi"] == 0 and lien.last_error is None


def test_instagram_seulement_les_posts_avec_le_hashtag(client, db_session, e, en_tant_que, photos, faux_instagram):
    """Seb, 11 novembre : seuls les posts avec #contretemps arrivent ; le
    réglage se fait avant même de relier le compte."""
    from datetime import datetime, timedelta, timezone

    from app.main import core
    from news.models import NewsInstagram

    eid = e["ecole"].id
    en_tant_que(e["seb"])
    url = f"/ecoles/{eid}/news/settings"
    assert client.get(url).json()["instagram_hashtag"] == ""
    # Le # et les espaces sont enlevés.
    assert client.put(url, json={"instagram_hashtag": " #ContreTemps "}).json()["instagram_hashtag"] == "ContreTemps"
    client.put(f"/ecoles/{eid}/news/instagram", json={"token": "IGAA" + "x" * 40})
    lien = db_session.get(NewsInstagram, eid)
    lien.linked_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
    db_session.commit()
    maintenant = datetime.now(timezone.utc)
    faux_instagram["posts"] = [
        _post("a", maintenant, caption="Gala samedi #contretemps", media_type="IMAGE", media_url="https://cdn/a.jpg"),
        _post("b", maintenant, caption="Mes vacances #contretempsdanse", media_type="IMAGE", media_url="https://cdn/b.jpg"),
        _post("c", maintenant, caption="Sans tag", media_type="IMAGE", media_url="https://cdn/c.jpg"),
    ]
    assert core.news_instagram.sync(db_session, lien) == 1
    assert [i.instagram_id for i in db_session.query(NewsItem).filter_by(org_id=eid)] == ["a"]


def test_instagram_posts_en_brouillon(client, db_session, e, en_tant_que, photos, faux_instagram):
    """Seb, 11 novembre : qui relie choisit si les posts sont publiés tout de
    suite ou arrivent en brouillon dans Édition."""
    from datetime import datetime, timedelta, timezone

    from app.main import core
    from news.models import NewsInstagram

    eid = e["ecole"].id
    en_tant_que(e["seb"])
    url = f"/ecoles/{eid}/news/settings"
    assert client.get(url).json()["instagram_publish"] is True
    assert client.put(url, json={"instagram_publish": False}).json()["instagram_publish"] is False
    client.put(f"/ecoles/{eid}/news/instagram", json={"token": "IGAA" + "x" * 40})
    lien = db_session.get(NewsInstagram, eid)
    lien.linked_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
    db_session.commit()
    faux_instagram["posts"] = [_post("d", datetime.now(timezone.utc), media_type="IMAGE", media_url="https://cdn/d.jpg")]
    assert core.news_instagram.sync(db_session, lien) == 1
    actu = db_session.query(NewsItem).filter_by(org_id=eid, instagram_id="d").one()
    assert actu.published_at is None
    assert client.get(f"/ecoles/{eid}/news").json()["items"] == []
