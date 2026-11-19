"""Drives du club (spec/core.md §3) : éteint par défaut, connexion d'un
kDrive comme une boîte mail, plusieurs drives, écoles étanches, parcourir
les dossiers. Aucun appel réseau : le client du drive est remplacé."""

import pytest
from ecoles import Ecoles

from drives.providers import DriveNotFound, DriveRefused, Entry

KDRIVE = {"provider": "kdrive", "address": "club@ik.me", "code": "bon-mot-de-passe", "drive_ref": "812345"}


class FauxDrive:
    def __init__(self, provider, address, secret, drive_ref):
        self.secret = secret

    def check(self):
        if self.secret not in ("bon-mot-de-passe", ""):
            raise DriveRefused("Infomaniak n'a pas accepté l'adresse ou le mot de passe d'application.")

    def list(self, path=""):
        if self.secret == "":
            raise DriveRefused("coupé")
        return [Entry(name="SALAIRES", path="FINANCIER/SALAIRES", is_dir=True)]


@pytest.fixture()
def ecole(db_session):
    return Ecoles().create(db_session, nom="Sambo La Ciotat", code_postal="13600")


@pytest.fixture(autouse=True)
def faux(monkeypatch):
    from app import main

    monkeypatch.setattr(main.core.drives, "factory", FauxDrive)


def test_eteint_par_defaut(db_session, ecole):
    from registry import activation

    assert "drives" in activation.disabled(db_session, ecole.id)


def test_connecter_renommer_deconnecter(client, db_session, ecole):
    from drives import DriveAccount

    url = f"/ecoles/{ecole.id}/drives"
    assert client.get(url).json()["connected"] is False
    refus = client.put(url, json={**KDRIVE, "code": "faux"})
    assert refus.status_code == 422 and "Infomaniak" in refus.json()["detail"]
    sans_numero = client.put(url, json={**KDRIVE, "drive_ref": ""})
    assert sans_numero.status_code == 422

    etat = client.put(url, json=KDRIVE).json()
    assert [(d["name"], d["provider"], d["address"]) for d in etat["drives"]] == [("Club", "kdrive", "club@ik.me")]
    ligne = db_session.query(DriveAccount).one()
    assert "bon-mot-de-passe" not in ligne.secret_encrypted

    # Un second drive, nommé.
    etat = client.put(url, json={**KDRIVE, "name": "Trésorerie"}).json()
    assert [d["name"] for d in etat["drives"]] == ["Club", "Trésorerie"]
    second = etat["drives"][1]["id"]
    etat = client.patch(f"{url}?drive={second}", json={"name": "Compta"}).json()
    assert [d["name"] for d in etat["drives"]] == ["Club", "Compta"]

    assert client.delete(f"{url}?drive={second}").status_code == 204
    assert [d["name"] for d in client.get(url).json()["drives"]] == ["Club"]


def test_parcourir_un_drive(client, ecole):
    url = f"/ecoles/{ecole.id}/drives"
    drive = client.put(url, json=KDRIVE).json()["drives"][0]["id"]
    liste = client.get(f"{url}/{drive}/list", params={"path": "FINANCIER"}).json()
    assert liste[0]["path"] == "FINANCIER/SALAIRES" and liste[0]["is_dir"] is True
    assert client.get(f"{url}/999/list").status_code == 409


def test_ecoles_etanches(client, db_session, ecole):
    url = f"/ecoles/{ecole.id}/drives"
    drive = client.put(url, json=KDRIVE).json()["drives"][0]["id"]
    autre = Ecoles().create(db_session, nom="Le Beausset", code_postal="83330")
    assert client.get(f"/ecoles/{autre.id}/drives").json()["drives"] == []
    assert client.get(f"/ecoles/{autre.id}/drives/{drive}/list").status_code == 409


def test_kdrive_par_l_api_d_infomaniak():
    """Seb, 19 novembre : my kSuite ferme WebDAV ; le kDrive passe par l'API
    d'Infomaniak avec un jeton. Lire, ouvrir, écrire ; jeton refusé."""
    import httpx

    from drives.providers import KDrive

    enfants = {
        1: [{"id": 5, "name": "Private", "type": "dir"}],
        5: [{"id": 7, "name": "FINANCIER", "type": "dir"}],
        7: [{"id": 9, "name": "SALAIRES", "type": "dir"},
            {"id": 11, "name": "Bulletin octobre.pdf", "type": "file", "size": 1234, "last_modified_at": 1762761600}],
    }
    vus = []

    def repondre(requete):
        vus.append((requete.method, requete.url.path, requete.headers.get("Authorization")))
        if requete.headers.get("Authorization") != "Bearer bon-jeton":
            return httpx.Response(401, json={"result": "error", "error": {"code": "not_authorized"}})
        morceaux = requete.url.path.split("/")
        if requete.url.path.endswith("/download"):
            return httpx.Response(200, content=b"%PDF bulletin")
        if requete.url.path.endswith("/upload"):
            assert requete.url.params["directory_id"] == "7" and requete.url.params["file_name"] == "a b.pdf"
            assert requete.content == b"%PDF"
            return httpx.Response(200, json={"result": "success", "data": {"id": 12}})
        if requete.url.path.endswith("/files") and len(morceaux) == 7:
            return httpx.Response(200, json={"result": "success", "data": enfants.get(int(morceaux[5]), []), "has_more": False})
        return httpx.Response(200, json={"result": "success", "data": {"id": 1}})

    client = httpx.Client(transport=httpx.MockTransport(repondre))
    drive = KDrive("club@ik.me", "bon-jeton", "1262779", http=client)
    drive.check()
    entrees = drive.list("Private/FINANCIER")
    assert [(e.name, e.path, e.is_dir, e.size) for e in entrees] == [
        ("SALAIRES", "Private/FINANCIER/SALAIRES", True, 0),
        ("Bulletin octobre.pdf", "Private/FINANCIER/Bulletin octobre.pdf", False, 1234),
    ]
    assert entrees[1].modified.year == 2025
    assert vus[0][1] == "/3/drive/1262779/files/1"
    assert drive.read("Private/FINANCIER/Bulletin octobre.pdf") == b"%PDF bulletin"
    assert drive.write("Private/FINANCIER", "a b.pdf", b"%PDF") == "Private/FINANCIER/a b.pdf"
    with pytest.raises(DriveNotFound):
        drive.list("Private/ABSENT")
    with pytest.raises(DriveRefused):
        KDrive("club@ik.me", "faux", "1262779", http=client).check()


def test_google_drive_propose_quand_le_serveur_a_la_cle(client, ecole, monkeypatch, tmp_path):
    """Étape 4 (import-auto-pieces.md) : sans clé, pas d'adresse à partager ;
    la clé posée par Seb sur le serveur suffit à proposer Google Drive."""
    from drives import providers

    monkeypatch.delenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE", raising=False)
    monkeypatch.setattr(providers, "KEY_FILE", str(tmp_path / "absent.json"))
    url = f"/ecoles/{ecole.id}/drives"
    assert client.get(url).json()["google_address"] is None

    cle = tmp_path / "google_drive.json"
    cle.write_text('{"client_email": "appli@club.iam.gserviceaccount.com", "private_key": "x"}')
    monkeypatch.setattr(providers, "KEY_FILE", str(cle))
    assert client.get(url).json()["google_address"] == "appli@club.iam.gserviceaccount.com"
