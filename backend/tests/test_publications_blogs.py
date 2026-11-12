"""Module Publications : plusieurs blogs, un droit par blog, les catégories
(spec/modules/actualites.md §12), et la migration qui fait d'Actualités le
blog « Actus » sans rien perdre (Seb, 12 novembre : actus publiées, Stellina
Revel publieuse, module allumé, Instagram relié)."""

from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from conftest import entetes_session

from comptes import Comptes
from ecoles import Ecoles
from groups import rights
from publications.publications import blogs_of, publish_right

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture()
def club(db_session):
    comptes = Comptes()
    ecole = Ecoles().create(db_session, nom="Fight Lab", code_postal="13600")
    owner = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Richard", prenom="Seb")
    prof = comptes.create(db_session, ecole_id=ecole.id, role="professeur", nom="Roux", prenom="Ana")
    eleve = comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="Martin", prenom="Zoé")
    db_session.commit()
    return {"ecole": ecole, "owner": owner, "prof": prof, "eleve": eleve,
            "base": f"/ecoles/{ecole.id}/publications/blogs"}


@pytest.mark.rbac_reel
def test_un_blog_techniques_a_cote_d_actus(client, db_session, club):
    owner, prof, eleve = (entetes_session(club[k]) for k in ("owner", "prof", "eleve"))
    base = club["base"]
    # Une école reçoit « Actus » à sa première visite.
    assert [b["name"] for b in client.get(base, headers=eleve).json()] == ["Actus"]
    # Seul l'Administrateur principal ajoute un blog (Fonctionnalités).
    assert client.post(base, json={"name": "Techniques"}, headers=prof).status_code == 403
    techniques = client.post(base, json={"name": "Techniques"}, headers=owner).json()
    assert (techniques["icon"], techniques["with_levels"], techniques["with_categories"]) == ("news", False, False)
    assert client.post(base, json={"name": " techniques "}, headers=owner).json()["detail"] == "« techniques » existe déjà"
    assert client.put(f"{base}/{techniques['id']}", json={"icon": "books", "with_categories": True}, headers=owner).json()["icon"] == "books"
    assert client.put(f"{base}/{techniques['id']}", json={"icon": "fusee"}, headers=owner).status_code == 400
    assert [b["name"] for b in client.get(base, headers=eleve).json()] == ["Actus", "Techniques"]

    # Le prof publie dans Techniques, pas dans Actus.
    rights.add(db_session, club["prof"], publish_right(techniques["id"]), "Publier dans Techniques")
    db_session.commit()
    actus = blogs_of(db_session, club["ecole"].id)[0]
    billet = {"body": "Garder le coude collé", "title": "Clé de bras en croix", "category": "Clés"}
    assert client.post(f"{base}/{techniques['id']}/posts", json=billet, headers=prof).status_code == 201
    assert client.post(f"{base}/{actus.id}/posts", json={"body": "x"}, headers=prof).status_code == 403
    blogs = {b["name"]: b for b in client.get(base, headers=prof).json()}
    assert blogs["Techniques"]["can_publish"] and not blogs["Actus"]["can_publish"]
    # Chaque blog a son fil.
    assert [p["title"] for p in client.get(f"{base}/{techniques['id']}", headers=eleve).json()["items"]] == ["Clé de bras en croix"]
    assert client.get(f"{base}/{actus.id}", headers=eleve).json()["items"] == []

    # Un blog qui a des publications ne se supprime pas ; le dernier non plus.
    assert client.delete(f"{base}/{techniques['id']}", headers=owner).status_code == 409
    vide = client.post(base, json={"name": "Vide"}, headers=owner).json()
    assert client.delete(f"{base}/{vide['id']}", headers=owner).status_code == 204


def test_l_appli_s_ouvre_sur_un_seul_blog(client, club):
    base = club["base"]
    actus = client.get(base).json()[0]
    techniques = client.post(base, json={"name": "Techniques"}).json()
    assert actus["open_app_on"] is True and techniques["open_app_on"] is False
    client.put(f"{base}/{techniques['id']}/settings", json={"open_app_on": True})
    assert [b["open_app_on"] for b in client.get(base).json()] == [False, True]


def test_niveaux_eteints_rien_n_est_efface(client, club):
    base = club["base"]
    actus = client.get(base).json()[0]
    url = f"{base}/{actus['id']}"
    importante = client.post(f"{url}/posts", json={"body": "Pas de cours", "level": "important",
                                                     "on_top_until": "2999-01-01"}).json()
    assert importante["on_top"] is True
    client.put(url, json={"with_levels": False})
    # Une carte Normal, et le niveau gardé pour quand on rallume.
    affichee = client.get(url).json()["items"][0]
    assert (affichee["level"], affichee["on_top"]) == ("normal", False)
    client.put(f"{url}/posts/{importante['id']}", json={"body": "Pas de cours lundi", "level": "normal"})
    client.put(url, json={"with_levels": True})
    assert client.get(url).json()["items"][0]["level"] == "important"


def test_categories_jamais_vides_renommer_et_reunir(client, club):
    base = club["base"]
    blog = client.post(base, json={"name": "Techniques"}).json()
    client.put(f"{base}/{blog['id']}", json={"with_categories": True})
    url = f"{base}/{blog['id']}"

    def publier(titre, categorie, sous=None, **kw):
        reponse = client.post(f"{url}/posts", json={"body": "…", "title": titre, "category": categorie,
                                                      "subcategory": sous, **kw})
        assert reponse.status_code == 201, reponse.text
        return reponse.json()

    # Un nom et une catégorie sont obligatoires.
    assert client.post(f"{url}/posts", json={"body": "x", "category": "Clés"}).json()["detail"] == "Donnez un nom"
    assert client.post(f"{url}/posts", json={"body": "x", "title": "Y"}).json()["detail"] == "Choisissez une catégorie"

    croix = publier("Clé de bras en croix", "Clés", "Bras")
    assert [c["name"] for c in croix["categories"]] == ["Clés", "Bras"]
    # Majuscules et accents ne distinguent pas deux catégories.
    publier("Clé de cheville", "cles", "Jambes")
    publier("Balayage intérieur", "Projections", publish=False)
    arbre = client.get(f"{url}/categories").json()
    assert [(c["name"], c["count"], [(s["name"], s["count"]) for s in c["children"]]) for c in arbre] == [
        ("Clés", 0, [("Bras", 1), ("Jambes", 1)]), ("Projections", 1, [])]

    # Renommer ; le nom d'une autre catégorie du même niveau réunit les deux.
    jambes = arbre[0]["children"][1]
    arbre = client.put(f"{url}/categories/{jambes['id']}", json={"name": "Jambe"}).json()
    assert [s["name"] for s in arbre[0]["children"]] == ["Bras", "Jambe"]
    arbre = client.put(f"{url}/categories/{jambes['id']}", json={"name": "bras"}).json()
    assert [(s["name"], s["count"]) for s in arbre[0]["children"]] == [("Bras", 2)]
    projections = arbre[1]
    arbre = client.put(f"{url}/categories/{projections['id']}", json={"name": "CLÉS"}).json()
    assert [(c["name"], c["count"]) for c in arbre] == [("Clés", 1)]

    # Une catégorie disparaît avec son dernier billet.
    for billet in client.get(url).json()["items"] + client.get(url).json()["drafts"]:
        client.delete(f"{url}/posts/{billet['id']}")
    assert client.get(f"{url}/categories").json() == []


def test_migration_actus_devient_un_blog_sans_rien_perdre(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'avant.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    command.upgrade(config, "c8f1a3e5d7b2")
    moteur = sa.create_engine(url)
    with moteur.begin() as c:
        x = lambda sql: c.execute(sa.text(sql))  # noqa: E731
        for ecole_id, nom in ((1, "Contretemps"), (2, "Fight Lab")):
            x(f"INSERT INTO ecoles (id, nom, code_postal, sous_domaine, created_at) VALUES ({ecole_id}, '{nom}', '83000', 'e{ecole_id}', CURRENT_TIMESTAMP)")
        # Contretemps : Stellina publie, deux actus (une avec photo), le
        # relais Instagram, le module allumé, ses réglages.
        x("INSERT INTO comptes (id, ecole_id, nom, prenom, created_at) VALUES (10, 1, 'Revel', 'Stellina', CURRENT_TIMESTAMP)")
        x("INSERT INTO comptes (id, ecole_id, nom, prenom, created_at) VALUES (20, 2, 'Roux', 'Ana', CURRENT_TIMESTAMP)")
        x("INSERT INTO groups (id, org_id, key, name, created_at) VALUES (5, 1, 'right.news.publish', 'Publier les actualités', CURRENT_TIMESTAMP)")
        x("INSERT INTO group_members (group_id, member_id, created_at) VALUES (5, 10, CURRENT_TIMESTAMP)")
        x("INSERT INTO org_modules (org_id, module_key, enabled, updated_at) VALUES (1, 'news', 1, CURRENT_TIMESTAMP)")
        x("INSERT INTO org_modules (org_id, module_key, enabled, updated_at) VALUES (2, 'news', 0, CURRENT_TIMESTAMP)")
        x("INSERT INTO news_items (id, org_id, level, body, notify, author_id, author_name, published_at, created_at, updated_at)"
          " VALUES (7, 1, 'important', 'Gala le 13', 1, 10, 'Stellina', '2026-11-10 10:00:00', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)")
        x("INSERT INTO news_items (id, org_id, level, body, notify, author_name, created_at, updated_at)"
          " VALUES (8, 1, 'normal', 'Brouillon', 0, 'Stellina', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)")
        x(f"INSERT INTO news_media (id, item_id, position, photo_sha) VALUES (3, 7, 0, '{'a' * 64}')")
        x("INSERT INTO news_seen (compte_id, seen_at) VALUES (10, '2026-11-11 08:00:00')")
        x("INSERT INTO news_settings (org_id, open_on_news, media_first, visible_to_all, instagram_hashtag, instagram_publish)"
          " VALUES (1, 1, 1, 1, 'contretemps', 0)")
        x("INSERT INTO news_instagram (org_id, token_encrypted, username, linked_by, linked_by_name, linked_at, token_refreshed_at, ig_user_id, refreshes)"
          " VALUES (1, 'chiffre', 'stellina_danse', 10, 'Stellina', '2026-11-11 09:00:00', '2026-11-11 09:00:00', '1784', 0)")

    command.upgrade(config, "head")

    with moteur.connect() as c:
        q = lambda sql: c.execute(sa.text(sql)).all()  # noqa: E731
        assert not {"news_items", "news_media", "news_seen", "news_settings", "news_instagram"} & set(sa.inspect(c).get_table_names())
        blogs = q("SELECT id, org_id, name, icon, with_levels, with_categories, open_app_on, media_first, visible_to_all FROM pub_blogs ORDER BY org_id")
        (actus, _, *reste), (actus2, *_) = blogs
        assert reste == ["Actus", "news", 1, 0, 1, 1, 1]
        assert blogs[1][2:] == ("Actus", "news", 1, 0, 1, 0, 1)
        assert q("SELECT id, blog_id, level, body, author_id, published_at IS NOT NULL FROM pub_posts ORDER BY id") == [
            (7, actus, "important", "Gala le 13", 10, 1), (8, actus, "normal", "Brouillon", None, 0)]
        assert q("SELECT post_id, photo_sha FROM pub_media") == [(7, "a" * 64)]
        assert q("SELECT compte_id, blog_id FROM pub_seen") == [(10, actus)]
        assert q("SELECT org_id, hashtag, publish FROM pub_instagram_settings") == [(1, "contretemps", 0)]
        assert q("SELECT org_id, blog_id, username, ig_user_id, refreshes FROM pub_instagram") == [(1, actus, "stellina_danse", "1784", 0)]
        # Stellina garde son droit, devenu « Publier dans Actus ».
        assert q("SELECT g.key, g.name, m.member_id FROM groups g JOIN group_members m ON m.group_id = g.id") == [
            (f"right.publications.publish.{actus}", "Publier dans Actus", 10)]
        # Le module garde son état : allumé chez Contretemps, éteint ailleurs.
        assert q("SELECT org_id, module_key, enabled FROM org_modules ORDER BY org_id") == [
            (1, "publications", 1), (2, "publications", 0)]
        assert actus2 != actus

    # Retour en arrière : la page d'actus revient, droit et module compris.
    command.downgrade(config, "c8f1a3e5d7b2")
    with moteur.connect() as c:
        q = lambda sql: c.execute(sa.text(sql)).all()  # noqa: E731
        assert q("SELECT id, body FROM news_items ORDER BY id") == [(7, "Gala le 13"), (8, "Brouillon")]
        assert q("SELECT key, name FROM groups") == [("right.news.publish", "Publier les actualités")]
        assert q("SELECT org_id, open_on_news, media_first, instagram_hashtag FROM news_settings ORDER BY org_id") == [
            (1, 1, 1, "contretemps"), (2, 1, 0, "")]
        assert {m for (m,) in q("SELECT module_key FROM org_modules")} == {"news"}
