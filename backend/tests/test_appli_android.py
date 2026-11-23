"""Appli Android d'une école (Seb 18/11/2026, spec/core.md §2.7 ter) :
réglable seulement avec Fights, fabriquée par l'action GitHub, proposée aux
adhérents Android. Rien ne change pour Le Beausset."""

import pytest
from app.main import MODULES
from ecoles import Ecoles
from personnalisation import appli_android
from registry.activation import set_enabled

ASC = "alliance-sambo-combat-la-ciotat"
RELEASE = "https://github.com/silvaplana/contretemps/releases/download/tournage-latest"


@pytest.fixture()
def github(monkeypatch):
    """La release et l'action GitHub, simulées."""
    etat = {"version": {}, "lancees": 0}
    monkeypatch.setattr(appli_android, "version_publiee", lambda: etat["version"])

    def lancer():
        etat["lancees"] += 1
        return True

    monkeypatch.setattr(appli_android, "lancer_fabrication", lancer)
    return etat


@pytest.fixture()
def beausset(db_session):
    return Ecoles().create(db_session, nom="Contretemps", code_postal="83330", sous_domaine="le-beausset")


@pytest.fixture()
def asc(client, db_session):
    ecole = Ecoles().create(db_session, nom="ASC La Ciotat", code_postal="13600", sous_domaine=ASC)
    client.patch(f"/ecoles/{ecole.id}/nature", json={"nature": "combat"})
    set_enabled(db_session, ecole.id, MODULES, "session_clips", True)
    return ecole


def test_le_beausset_n_a_pas_d_appli(client, db_session, beausset, github):
    set_enabled(db_session, beausset.id, MODULES, "session_clips", False)
    assert client.get(f"/ecoles/{beausset.id}/appli-android").json() == {
        "disponible": False, "actif": False, "prete": False, "url": None, "date": None,
    }
    # Sans Fights, le réglage est refusé.
    assert client.put(f"/ecoles/{beausset.id}/appli-android", json={"actif": True}).status_code == 400
    assert client.get("/applis-android").json() == []
    assert github["lancees"] == 0


def test_oui_fabrique_l_appli_puis_la_propose(client, asc, github):
    etat = client.put(f"/ecoles/{asc.id}/appli-android", json={"actif": True}).json()
    assert (etat["actif"], etat["prete"], github["lancees"]) == (True, False, 1)
    assert client.get("/applis-android").json() == [
        {"cle": ASC, "nom": "ASC La Ciotat", "adresse": f"https://{ASC}.assofight.silvaplana.cloud"}
    ]
    # L'action a publié l'appli : elle est prête, avec son lien.
    github["version"] = {"build": 40, "date": "18/11", "apk": {ASC: f"{RELEASE}/tournage-{ASC}.apk"}}
    etat = client.get(f"/ecoles/{asc.id}/appli-android").json()
    assert (etat["prete"], etat["url"], etat["date"]) == (True, f"{RELEASE}/tournage-{ASC}.apk", "18/11")


def test_non_garde_le_nom_de_l_appli(client, db_session, asc, github):
    client.put(f"/ecoles/{asc.id}/appli-android", json={"actif": True})
    client.put(f"/ecoles/{asc.id}/appli-android", json={"actif": False})
    assert client.get("/applis-android").json() == []
    asc.sous_domaine = "asc"
    db_session.commit()
    client.put(f"/ecoles/{asc.id}/appli-android", json={"actif": True})
    # Même nom qu'au premier « Oui » : les applis installées se mettent à jour.
    assert client.get("/applis-android").json()[0]["cle"] == ASC


def test_eteindre_fights_retire_l_appli_de_la_liste(client, db_session, asc, github):
    client.put(f"/ecoles/{asc.id}/appli-android", json={"actif": True})
    set_enabled(db_session, asc.id, MODULES, "session_clips", False)
    assert client.get("/applis-android").json() == []
    assert client.get(f"/ecoles/{asc.id}/appli-android").json()["disponible"] is False


def test_inviter_un_administrateur_sur_l_appli_android(client, db_session, asc, github, mails):
    """Le mail garde « Activer mon accès », puis ajoute le lien de l'appli
    Android et comment l'installer (Seb 18/11/2026)."""
    from comptes import Comptes

    admin = Comptes().create(db_session, ecole_id=asc.id, role="eleve", nom="Dupont", prenom="Léo", email="leo@x.fr")
    route = f"/ecoles/{asc.id}/invitations"
    # Appli pas encore publiée : refusé, rien ne part.
    client.put(f"/ecoles/{asc.id}/appli-android", json={"actif": True})
    assert client.post(route, json={"compte_ids": [admin.id], "appli_android": True}).status_code == 409
    assert mails == []

    apk = f"{RELEASE}/tournage-{ASC}.apk"
    github["version"] = {"build": 40, "date": "18/11", "apk": {ASC: apk}}
    assert client.post(route, json={"compte_ids": [admin.id], "appli_android": True}).status_code == 200
    _, _, texte, html = mails[-1]
    # Un seul lien, celui du site (Seb 23/11) : il proposera l'appli Android une fois connecté.
    assert "d'installer l'appli « Tournage ASC La Ciotat »" in texte
    assert texte.count("https://") == 1 and "&appli=android\n" in texte
    assert apk not in texte and apk not in html

    # « Appli normale » : le mail de toujours, sans l'appli Android.
    client.post(route, json={"compte_ids": [admin.id]})
    assert "appli=android" not in mails[-1][2] and "Tournage" not in mails[-1][2] and "Activer mon accès" in mails[-1][2]


def test_le_beausset_ne_peut_pas_inviter_sur_l_appli_android(client, db_session, beausset, github, mails):
    from comptes import Comptes

    admin = Comptes().create(db_session, ecole_id=beausset.id, role="eleve", nom="Roux", prenom="Ana", email="ana@x.fr")
    route = f"/ecoles/{beausset.id}/invitations"
    assert client.post(route, json={"compte_ids": [admin.id], "appli_android": True}).status_code == 409
    assert client.post(route, json={"compte_ids": [admin.id]}).status_code == 200
    assert "appli=android" not in mails[-1][2]
