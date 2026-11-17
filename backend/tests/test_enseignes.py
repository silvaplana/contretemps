"""Enseignes (Seb 17/11/2026, spec/core.md §2.7 bis) : un seul serveur,
Contretemps pour la danse et Assofight pour le combat, chacune sur son
domaine. Contretemps et Le Beausset ne changent en rien."""

import pytest
from app.main import auth_receiver
from comptes import Comptes
from conftest import MOT_DE_PASSE, donner_mot_de_passe
from ecoles import Ecoles
from personnalisation import brands

BEAUSSET = "le-beausset.contretemps.silvaplana.cloud"
ASSO = "alliance-sambo-combat-la-ciotat"


@pytest.fixture()
def beausset(db_session):
    return Ecoles().create(db_session, nom="Contretemps", code_postal="83330", sous_domaine="le-beausset")


@pytest.fixture()
def asc(client, db_session):
    ecole = Ecoles().create(db_session, nom="ASC La Ciotat", code_postal="13600", sous_domaine=ASSO)
    assert client.patch(f"/ecoles/{ecole.id}/nature", json={"nature": "combat"}).status_code == 200
    db_session.refresh(ecole)
    return ecole


def test_le_beausset_ne_change_pas(client, beausset, asc):
    vue = client.get("/par-host/personnalisation", headers={"Host": BEAUSSET}).json()
    assert beausset.nature == "danse"
    assert (vue["adresse"], vue["redirige_vers"], vue["nom_appli"], vue["slogan"]) == (
        "https://le-beausset.contretemps.silvaplana.cloud", None, "Contretemps", "Gestion d'école de danse du cours au gala",
    )
    assert (vue["couleur_fond"], vue["couleur_texte"], vue["couleur_accent"]) == ("#FDECD8", "#3A2410", "#D8722A")
    assert client.get("/par-host/site.webmanifest", headers={"Host": BEAUSSET}).json()["theme_color"] == "#F46E19"
    icone = client.get("/par-host/icons/icon-192.png", headers={"Host": BEAUSSET}).content
    assert icone == (brands.CONTRETEMPS.defaults_dir / "icon-192.png").read_bytes()
    assert client.get(f"/ecoles/{beausset.id}/personnalisation/logo.png").content == (
        brands.CONTRETEMPS.defaults_dir / "logo-contretemps.png"
    ).read_bytes()
    generique = client.get("/par-host/personnalisation", headers={"Host": "app.contretemps.silvaplana.cloud"}).json()
    assert (generique["nom"], generique["couleur_fond"]) == ("Contretemps", "#FDECD8")
    mails = auth_receiver.invitations.mails
    assert mails.lien("activer", "J", "le-beausset", beausset.nature) == "https://le-beausset.contretemps.silvaplana.cloud/activer?jeton=J"


def test_le_mail_de_contretemps_garde_son_expediteur(monkeypatch, beausset, asc):
    envoyes = []
    mails = auth_receiver.invitations.mails
    monkeypatch.setattr(mails.envoi, "actif", True)
    monkeypatch.setattr(mails.envoi, "envoyer_confirmation", lambda *a, **k: envoyes.append(k["expediteur"]))
    mails.reinitialisation("a@x.fr", beausset.nom, "A B", "J", beausset.sous_domaine, beausset.nature)
    mails.reinitialisation("a@x.fr", asc.nom, "A B", "J", asc.sous_domaine, asc.nature)
    # (None, None) : l'expéditeur du serveur, comme avant les enseignes.
    assert envoyes == [(None, None), ("Assofight", "assofight@silvaplana.cloud")]


def test_une_ecole_de_combat_passe_sur_assofight(client, asc):
    vue = client.get("/par-host/personnalisation", headers={"Host": f"{ASSO}.assofight.silvaplana.cloud"}).json()
    assert (vue["adresse"], vue["redirige_vers"], vue["enseigne"]) == (
        f"https://{ASSO}.assofight.silvaplana.cloud", None, "assofight",
    )
    assert (vue["couleur_fond"], vue["couleur_accent"], vue["slogan"]) == (
        "#16171D", "#F4EA4B", "Gestion et enseignement pour association de sports de combat",
    )
    # L'ancienne adresse renvoie vers la nouvelle.
    ancienne = client.get("/par-host/personnalisation", headers={"Host": f"{ASSO}.contretemps.silvaplana.cloud"}).json()
    assert ancienne["redirige_vers"] == f"https://{ASSO}.assofight.silvaplana.cloud"
    assert client.get("/par-host/icons/icon-192.png", headers={"Host": f"{ASSO}.assofight.silvaplana.cloud"}).content == (
        brands.ASSOFIGHT.defaults_dir / "icon-192.png"
    ).read_bytes()


def test_les_liens_des_mails_d_une_ecole_de_combat(client, db_session, asc, mails):
    eleve = Comptes().create(db_session, ecole_id=asc.id, role="eleve", nom="Cilpa", prenom="Jacqueline", email="j@x.fr")
    client.post(f"/ecoles/{asc.id}/invitations", json={"compte_ids": [eleve.id]})
    assert f"https://{ASSO}.assofight.silvaplana.cloud/activer?jeton=" in mails[-1][2]


def test_chaque_domaine_n_affiche_que_ses_ecoles(client, db_session, beausset, asc):
    def noms(host=None):
        return {e["nom"] for e in client.get("/ecoles", headers={"Host": host} if host else {}).json()}

    assert noms("app.assofight.silvaplana.cloud") == {"ASC La Ciotat"}
    assert noms("app.contretemps.silvaplana.cloud") == {"Contretemps"}
    assert noms() == {"Contretemps", "ASC La Ciotat"}
    generique = client.get("/par-host/personnalisation", headers={"Host": "app.assofight.silvaplana.cloud"}).json()
    assert (generique["nom"], generique["couleur_fond"], generique["ecole_id"]) == ("Assofight", "#16171D", None)

    # Une personne inscrite dans les deux : chaque domaine ouvre son école.
    comptes = Comptes()
    danse = comptes.create(db_session, ecole_id=beausset.id, role="eleve", nom="Silpa", prenom="Jacqueline", email="j@x.fr")
    combat = comptes.create(db_session, ecole_id=asc.id, role="eleve", nom="Silpa", prenom="Jacqueline", email="j@x.fr")
    donner_mot_de_passe(db_session, "j@x.fr")
    corps = {"identifiant": "j@x.fr", "mot_de_passe": MOT_DE_PASSE}
    assert client.post("/auth/login", json=corps, headers={"Host": "app.assofight.silvaplana.cloud"}).json()["compte"]["id"] == combat.id
    assert client.post("/auth/login", json=corps, headers={"Host": "app.contretemps.silvaplana.cloud"}).json()["compte"]["id"] == danse.id
    assert len(client.post("/auth/login", json=corps).json()["choix"]) == 2


def test_une_ecole_creee_sur_assofight_est_de_combat(client):
    reponse = client.post(
        "/ecoles", json={"nom": "Club Boxe", "code_postal": "75001"}, headers={"Host": "app.assofight.silvaplana.cloud"}
    )
    assert reponse.status_code in (200, 201)
    ecole_id = reponse.json()["id"]
    assert client.get(f"/ecoles/{ecole_id}/apparence").json()["nature"] == "combat"
    autre = client.post("/ecoles", json={"nom": "Danse Lyon", "code_postal": "69003"}).json()
    assert client.get(f"/ecoles/{autre['id']}/apparence").json()["nature"] == "danse"


def test_nature_inconnue_refusee(client, beausset):
    assert client.patch(f"/ecoles/{beausset.id}/nature", json={"nature": "type"}).status_code == 400
