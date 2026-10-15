"""Personnalisation par école (spec §2.7, §5.1.1) : adresse web, ce que lit
le téléphone à l'installation (manifest, icônes), images et détourage."""

import io
import shutil

import pytest
from app.main import personnalisation_client
from comptes import Comptes
from ecoles import Ecoles
from personnalisation.adresse import AdresseInvalide, normaliser, verifier
from personnalisation.personnalisation import DOSSIER_PERSONNALISATION, etiquette_du_host
from PIL import Image, ImageDraw

HOTE = "le-beausset.contretemps.silvaplana.cloud"


@pytest.fixture()
def ecole(db_session):
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330", sous_domaine="le-beausset")
    shutil.rmtree(DOSSIER_PERSONNALISATION / str(ecole.id), ignore_errors=True)
    yield ecole
    shutil.rmtree(DOSSIER_PERSONNALISATION / str(ecole.id), ignore_errors=True)


def _logo_sur_fond_blanc() -> bytes:
    image = Image.new("RGB", (300, 300), "white")
    ImageDraw.Draw(image).ellipse((60, 60, 240, 240), fill=(216, 114, 42))
    sortie = io.BytesIO()
    image.save(sortie, format="PNG")
    return sortie.getvalue()


def test_regle_des_adresses():
    assert normaliser("Danse Lyon 3e") == "danse-lyon-3e"
    assert normaliser("  École  d'Été !! ") == "ecole-d-ete"
    assert verifier("Le Beausset") == "le-beausset"
    for adresse, raison in (("ab", "invalide"), ("contretemps", "reserve"), ("APP", "reserve"), ("---", "invalide")):
        with pytest.raises(AdresseInvalide) as erreur:
            verifier(adresse)
        assert erreur.value.raison == raison
    assert etiquette_du_host("Le-Beausset.contretemps.silvaplana.cloud:443") == "le-beausset"
    assert etiquette_du_host("le-beausset.localhost:5173") == "le-beausset"
    assert etiquette_du_host("silvaplana.cloud") is None
    assert etiquette_du_host("a.b.contretemps.silvaplana.cloud") is None


def test_adresse_proposee_a_la_creation(db_session):
    ecoles = Ecoles()
    # « contretemps » est réservé : la ville, sinon nom-code postal.
    assert ecoles.create(db_session, nom="Contretemps", code_postal="83330", ville="Le Beausset").sous_domaine == "le-beausset"
    assert ecoles.create(db_session, nom="Contretemps", code_postal="69003").sous_domaine == "contretemps-69003"
    assert ecoles.create(db_session, nom="Danse Lyon 3e", code_postal="69003").sous_domaine == "danse-lyon-3e"
    assert ecoles.create(db_session, nom="Danse Lyon 3e", code_postal="69004").sous_domaine == "danse-lyon-3e-69004"
    with pytest.raises(ValueError):
        ecoles.create(db_session, nom="Autre", code_postal="1", sous_domaine="danse-lyon-3e")


def test_disponibilite(client, ecole):
    libre = client.get("/sous-domaines/Danse Lyon/disponible").json()
    assert libre == {"adresse": "danse-lyon", "disponible": True, "raison": None, "proposition": None}
    prise = client.get("/sous-domaines/le-beausset/disponible").json()
    assert (prise["disponible"], prise["raison"], prise["proposition"]) == (False, "pris", "le-beausset-2")
    # Sa propre adresse est disponible pour elle-même.
    assert client.get("/sous-domaines/le-beausset/disponible", params={"ecole_id": ecole.id}).json()["disponible"]
    assert client.get("/sous-domaines/contretemps/disponible").json()["raison"] == "reserve"
    assert client.get("/sous-domaines/ab/disponible").json()["raison"] == "invalide"


def test_caddy_demande_si_l_adresse_existe(client, ecole):
    assert client.get("/sous-domaines/existe", params={"domain": HOTE}).status_code == 200
    assert client.get("/sous-domaines/existe", params={"domain": "app.contretemps.silvaplana.cloud"}).status_code == 200
    assert client.get("/sous-domaines/existe", params={"domain": "inventee.contretemps.silvaplana.cloud"}).status_code == 404
    assert client.get("/sous-domaines/existe", params={"domain": "exemple.com"}).status_code == 404


def test_ce_que_lit_le_telephone(client, ecole):
    vue = client.get("/par-host/personnalisation", headers={"Host": HOTE}).json()
    assert (vue["ecole_id"], vue["nom_appli"], vue["couleur_fond"]) == (ecole.id, "Contretemps", "#FDECD8")
    generique = client.get("/par-host/personnalisation", headers={"Host": "app.contretemps.silvaplana.cloud"}).json()
    assert generique["ecole_id"] is None

    client.patch(f"/ecoles/{ecole.id}/personnalisation", json={"nom_appli": "Danse Beausset", "slogan": "Danser ensemble"})
    manifest = client.get("/par-host/site.webmanifest", headers={"Host": HOTE})
    assert manifest.headers["cache-control"] == "no-cache"
    corps = manifest.json()
    assert (corps["name"], corps["short_name"], corps["description"], corps["start_url"]) == (
        "Danse Beausset", "Danse Beausset", "Danser ensemble", "/",
    )
    assert [i["src"].split("?")[0] for i in corps["icons"]] == [
        "/icons/icon-192.png", "/icons/icon-192-maskable.png", "/icons/icon-512.png", "/icons/icon-512-maskable.png",
    ]
    entete = client.get("/par-host/entete.html", headers={"Host": HOTE}).text
    assert "<title>Danse Beausset</title>" in entete and 'content="Danse Beausset"' in entete
    # Sans logo ni fond personnalisés : l'icône d'aujourd'hui.
    icone = client.get("/par-host/icons/icon-192.png", headers={"Host": HOTE})
    assert icone.status_code == 200 and Image.open(io.BytesIO(icone.content)).size == (192, 192)
    assert client.get("/par-host/icons/inconnue.png", headers={"Host": HOTE}).status_code == 404


def test_couleurs_police_et_refus(client, ecole):
    ok = client.patch(f"/ecoles/{ecole.id}/personnalisation", json={"couleur_fond": "#0a1b2c", "police": "poppins"})
    assert (ok.json()["couleur_fond"], ok.json()["police"]) == ("#0A1B2C", "poppins")
    assert client.patch(f"/ecoles/{ecole.id}/personnalisation", json={"couleur_fond": "rouge"}).status_code == 400
    assert client.patch(f"/ecoles/{ecole.id}/personnalisation", json={"police": "comic"}).status_code == 400
    assert client.patch(f"/ecoles/{ecole.id}/personnalisation", json={"slogan": "x" * 81}).status_code == 400
    # Fond personnalisé : l'icône est fabriquée sur cette couleur.
    icone = Image.open(io.BytesIO(client.get("/par-host/icons/icon-512.png", headers={"Host": HOTE}).content)).convert("RGB")
    assert icone.getpixel((2, 2)) == (10, 27, 44)


def test_logo_envoye_detoure_puis_valide(client, ecole):
    envoi = client.post(
        f"/ecoles/{ecole.id}/personnalisation/images/logo",
        files={"fichier": ("logo.png", _logo_sur_fond_blanc(), "image/png")},
    )
    assert envoi.status_code == 200
    brouillon = envoi.json()
    # Fond blanc uni : détourage « simple » par défaut, et le blanc proposé comme fond de l'appli.
    assert (brouillon["detourage"], brouillon["couleur_fond_proposee"]) == ("simple", "#FFFFFF")
    traite = Image.open(io.BytesIO(client.get(f"/ecoles/{ecole.id}/personnalisation/{brouillon['traite']}").content))
    assert traite.getpixel((0, 0))[3] == 0  # coin devenu transparent
    assert traite.size[0] < 300  # marges retirées
    assert client.get(f"/ecoles/{ecole.id}/personnalisation/{brouillon['original']}").status_code == 200

    # Changer d'avis sur le détourage, sans renvoyer l'image.
    aucun = client.post(f"/ecoles/{ecole.id}/personnalisation/images/logo/detourage", json={"detourage": "aucun"}).json()
    assert Image.open(io.BytesIO(client.get(f"/ecoles/{ecole.id}/personnalisation/{aucun['traite']}").content)).getpixel((0, 0))[3] == 255
    assert client.post(f"/ecoles/{ecole.id}/personnalisation/images/logo/detourage", json={"detourage": "magie"}).status_code == 400

    valide = client.post(f"/ecoles/{ecole.id}/personnalisation/images/logo/valider").json()
    assert valide["logo_personnalise"] is True
    assert client.get(f"/ecoles/{ecole.id}/personnalisation/logo.png").status_code == 200
    # Plus de brouillon après validation.
    assert client.get(f"/ecoles/{ecole.id}/personnalisation/{aucun['traite']}").status_code == 404
    # Avec un logo, l'icône est fabriquée (logo sur le fond de l'appli).
    icone = Image.open(io.BytesIO(client.get("/par-host/icons/icon-192.png", headers={"Host": HOTE}).content)).convert("RGB")
    assert icone.getpixel((1, 1)) == (0xFD, 0xEC, 0xD8)


def test_image_refusee(client, ecole):
    assert client.post(
        f"/ecoles/{ecole.id}/personnalisation/images/logo", files={"fichier": ("x.txt", b"bonjour", "text/plain")}
    ).status_code == 400
    assert client.post(
        f"/ecoles/{ecole.id}/personnalisation/images/logo", files={"fichier": ("x.png", b"pas une image", "image/png")}
    ).status_code == 400
    assert client.post(f"/ecoles/{ecole.id}/personnalisation/images/logo/valider").status_code == 400


def test_revenir_au_defaut_garde_l_adresse(client, ecole):
    client.patch(f"/ecoles/{ecole.id}/personnalisation", json={"couleur_accent": "#112233", "slogan": "Hop", "nom_appli": "Beausset"})
    vue = client.post(f"/ecoles/{ecole.id}/personnalisation/defaut").json()
    assert (vue["couleur_accent"], vue["slogan"], vue["sous_domaine"], vue["nom_appli"]) == (
        "#D8722A", "Gestion d'école de danse du cours au gala", "le-beausset", "Beausset",
    )


def test_changer_d_adresse_l_ancienne_redirige(client, db_session, ecole):
    vue = client.patch(f"/ecoles/{ecole.id}/sous-domaine", json={"sous_domaine": "Danse Beausset"}).json()
    assert vue["sous_domaine"] == "danse-beausset"
    ancienne = client.get("/par-host/personnalisation", headers={"Host": HOTE}).json()
    assert ancienne["redirige_vers"] == "https://danse-beausset.contretemps.silvaplana.cloud"
    assert client.get("/sous-domaines/existe", params={"domain": HOTE}).status_code == 200
    # L'ancienne adresse reste réservée tant qu'elle redirige.
    assert client.get("/sous-domaines/le-beausset/disponible").json()["raison"] == "pris"
    autre = Ecoles().create(db_session, nom="Autre", code_postal="11111")
    assert client.patch(f"/ecoles/{autre.id}/sous-domaine", json={"sous_domaine": "le-beausset"}).status_code == 409
    assert client.patch(f"/ecoles/{ecole.id}/sous-domaine", json={"sous_domaine": "app"}).status_code == 400
    # Revenir à l'ancienne adresse annule la redirection.
    assert client.patch(f"/ecoles/{ecole.id}/sous-domaine", json={"sous_domaine": "le-beausset"}).json()["sous_domaine"] == "le-beausset"


@pytest.mark.rbac_reel
def test_droits(client, db_session, ecole):
    from conftest import entetes_session

    comptes = Comptes()
    # Le premier admin d'une école en est l'Owner (spec §2.4).
    owner = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="A", prenom="Owner")
    admin = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="B", prenom="Admin")
    eleve = comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="C", prenom="Zoé")

    # Sans connexion : ce que lit le téléphone, rien d'autre.
    assert client.get("/par-host/personnalisation", headers={"Host": HOTE}).status_code == 200
    assert client.get("/par-host/site.webmanifest", headers={"Host": HOTE}).status_code == 200
    assert client.get(f"/ecoles/{ecole.id}/personnalisation/logo.png").status_code == 200
    assert client.patch(f"/ecoles/{ecole.id}/personnalisation", json={"slogan": "x"}).status_code == 401

    assert client.patch(f"/ecoles/{ecole.id}/personnalisation", json={"slogan": "x"}, headers=entetes_session(eleve)).status_code == 403
    assert client.patch(f"/ecoles/{ecole.id}/personnalisation", json={"slogan": "x"}, headers=entetes_session(admin)).status_code == 200
    # L'adresse : les Owners seulement.
    corps = {"sous_domaine": "nouvelle-adresse"}
    assert client.patch(f"/ecoles/{ecole.id}/sous-domaine", json=corps, headers=entetes_session(admin)).status_code == 403
    assert client.patch(f"/ecoles/{ecole.id}/sous-domaine", json=corps, headers=entetes_session(owner)).status_code == 200


def test_connexion_sur_l_adresse_de_l_ecole(client, db_session, ecole, monkeypatch):
    """Sur l'adresse d'une école, ses profils d'abord ; l'adresse de l'école
    est renvoyée pour y emmener la personne (une fois les adresses en service)."""
    from app.main import auth_receiver
    from conftest import MOT_DE_PASSE, donner_mot_de_passe

    autre = Ecoles().create(db_session, nom="Autre", code_postal="11111")
    comptes = Comptes()
    ici = comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="Martin", prenom="Zoé", email="zoe@example.com")
    comptes.create(db_session, ecole_id=autre.id, role="eleve", nom="Martin", prenom="Zoé", email="zoe@example.com")
    donner_mot_de_passe(db_session, "zoe@example.com")
    corps = {"identifiant": "zoe@example.com", "mot_de_passe": MOT_DE_PASSE}

    assert len(client.post("/auth/login", json=corps).json()["choix"]) == 2
    sur_l_ecole = client.post("/auth/login", json=corps, headers={"Host": HOTE}).json()
    assert sur_l_ecole["compte"]["id"] == ici.id and sur_l_ecole["adresse_ecole"] is None

    monkeypatch.setattr(auth_receiver.invitations.mails, "adresse_par_ecole", True)
    sur_l_ecole = client.post("/auth/login", json=corps, headers={"Host": HOTE}).json()
    assert sur_l_ecole["adresse_ecole"] == "https://le-beausset.contretemps.silvaplana.cloud"
    assert auth_receiver.invitations.mails.lien("activer", "J", "le-beausset") == (
        "https://le-beausset.contretemps.silvaplana.cloud/activer?jeton=J"
    )
