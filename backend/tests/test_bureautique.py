"""Édition Word / Excel / PowerPoint avec OnlyOffice (essai) : configuration
signée, lecture du fichier par OnlyOffice, retour du fichier modifié qui
devient une nouvelle version. Faux serveur OnlyOffice (aucun réseau)."""

import io
import json

import pytest
from app import main
from bureautique import bureautique as module
from bureautique.bureautique import jwt_lire, jwt_signer
from comptes import Comptes, rbac
from conftest import MOT_DE_PASSE, entetes_session
from ecoles import Ecoles
from securite import mots_de_passe

pytestmark = pytest.mark.rbac_reel
SECRET = "secret-onlyoffice-des-tests"


@pytest.fixture()
def monde(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(main.documents_client.storage, "root", tmp_path)
    monkeypatch.setenv("ONLYOFFICE_JWT_SECRET", SECRET)
    monkeypatch.setenv("ONLYOFFICE_URL", "https://silvaplana.cloud/onlyoffice")
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    admin = Comptes().create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia")
    Comptes().enregistrer_superuser(
        db_session, nom="Richard", prenom="Sébastien", email="su@test.fr",
        mot_de_passe_hache=mots_de_passe.hacher(MOT_DE_PASSE),
    )
    return {"ecole": ecole, "admin": admin}


def _superuser(client, db_session):
    from comptes.models import Compte

    jeton = client.post("/auth/login", json={"identifiant": "Sébastien Richard", "mot_de_passe": MOT_DE_PASSE}).json()["jeton"]
    su = next(c for c in db_session.query(Compte).all() if c.a_l_email("su@test.fr"))
    return {"Authorization": f"Bearer {jeton}", rbac.ENTETE_COMPTE: str(su.id)}


def test_ouvrir_modifier_et_enregistrer(client, db_session, monde, monkeypatch):
    entetes = _superuser(client, db_session)
    base = f"/documents/orgs/{monde['ecole'].id}"
    fichier = client.post(
        f"{base}/files", data={"space": "public"}, files={"file": ("Budget.xlsx", io.BytesIO(b"PK version 1"))}, headers=entetes,
    ).json()

    reponse = client.get(f"/bureautique/orgs/{monde['ecole'].id}/nodes/{fichier['id']}/configuration", headers=entetes)
    assert reponse.status_code == 200
    corps = reponse.json()
    config = corps["config"]
    assert corps["api_js"] == "https://silvaplana.cloud/onlyoffice/web-apps/apps/api/documents/api.js"
    assert (config["documentType"], config["editorConfig"]["mode"], config["document"]["fileType"]) == ("cell", "edit", "xlsx")
    # Signée avec la clé partagée : OnlyOffice refuse une configuration non signée.
    signe = jwt_lire(config.pop("token"), SECRET)
    assert signe == config

    # OnlyOffice lit le fichier, sans session, grâce au jeton de l'adresse.
    adresse = config["document"]["url"].split("/api", 1)[1]
    assert client.get(adresse).content == b"PK version 1"
    assert client.get(adresse[:-3] + "abc").status_code == 403

    # Retour d'OnlyOffice : le fichier modifié devient une nouvelle version.
    monkeypatch.setattr(module.urllib.request, "urlopen", lambda url, timeout: io.BytesIO(b"PK version 2"))
    retour = config["editorConfig"]["callbackUrl"].split("/api", 1)[1]
    charge = {"status": 2, "key": config["document"]["key"], "url": "https://silvaplana.cloud/onlyoffice/cache/files/x/output.xlsx"}
    assert client.post(retour, json={**charge, "token": jwt_signer(charge, SECRET)}).json() == {"error": 0}
    assert client.get(f"{base}/nodes/{fichier['id']}/content", headers=entetes).content == b"PK version 2"
    # Un retour mal signé, ou d'une autre adresse, est refusé.
    assert client.post(retour, json={**charge, "token": jwt_signer(charge, "autre")}).json() == {"error": 1}
    pirate = {**charge, "url": "https://ailleurs.example/x.xlsx"}
    assert client.post(retour, json={**pirate, "token": jwt_signer(pirate, SECRET)}).json() == {"error": 1}


def test_reserve_au_superuser(client, monde):
    reponse = client.get(f"/bureautique/orgs/{monde['ecole'].id}/nodes/1/configuration", headers=entetes_session(monde["admin"]))
    assert reponse.status_code == 403
