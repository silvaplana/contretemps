"""Module HelloAsso, étape 8a : la connexion (spec/modules/helloasso.md §2).
Aucun appel réseau : `Connection.connect` est remplacé."""

import pytest
from comptes import Comptes
from conftest import entetes_session
from ecoles import Ecoles

CLES = {"client_id": "3f9c2a", "client_secret": "le-secret"}


@pytest.fixture()
def ecole(db_session):
    return Ecoles().create(db_session, nom="Sambo La Ciotat", code_postal="13600")


@pytest.fixture()
def helloasso(monkeypatch):
    from app import main
    from helloasso.api import HelloAssoError, Organization

    appels = []

    def connect(client_id, client_secret):
        appels.append((client_id, client_secret))
        if "faux" in client_secret:
            raise HelloAssoError("HelloAsso refuse ces clés.")
        return Organization(name="Alliance Sambo", slug="alliance-sambo", forms=["Adhésion 2026-2027"])

    monkeypatch.setattr(main.core.helloasso_connection, "connect", connect)
    return appels


def test_tester_enregistrer_retester_deconnecter(client, db_session, ecole, helloasso):
    from helloasso import OrgHelloAsso

    assert client.get(f"/ecoles/{ecole.id}/helloasso").json() == {
        "connected": False, "org_name": None, "connected_at": None,
    }
    faux = client.post(f"/ecoles/{ecole.id}/helloasso/tester", json={**CLES, "client_secret": "faux"})
    assert faux.status_code == 422 and faux.json()["detail"] == "HelloAsso refuse ces clés."
    ok = client.post(f"/ecoles/{ecole.id}/helloasso/tester", json={**CLES, "client_id": " 3f9c2a "}).json()
    assert ok == {"name": "Alliance Sambo", "forms": ["Adhésion 2026-2027"]}
    # Tester n'enregistre rien.
    assert client.get(f"/ecoles/{ecole.id}/helloasso").json()["connected"] is False

    assert client.put(f"/ecoles/{ecole.id}/helloasso", json=CLES).status_code == 200
    etat = client.get(f"/ecoles/{ecole.id}/helloasso").json()
    assert (etat["connected"], etat["org_name"]) == (True, "Alliance Sambo")
    # La clé secrète est chiffrée en base, et se relit pour retester.
    ligne = db_session.query(OrgHelloAsso).one()
    assert "le-secret" not in ligne.secret_encrypted
    assert client.post(f"/ecoles/{ecole.id}/helloasso/retester").status_code == 200
    assert helloasso[-1] == ("3f9c2a", "le-secret")

    # Déconnecter, puis Annuler.
    assert client.delete(f"/ecoles/{ecole.id}/helloasso").status_code == 204
    assert client.get(f"/ecoles/{ecole.id}/helloasso").json()["connected"] is False
    assert client.post(f"/ecoles/{ecole.id}/helloasso/retester").status_code == 422
    assert client.post(f"/ecoles/{ecole.id}/helloasso/reprendre").status_code == 204
    assert client.get(f"/ecoles/{ecole.id}/helloasso").json()["connected"] is True


def test_cle_illisible_si_le_secret_du_serveur_change(client, db_session, ecole, helloasso, monkeypatch):
    from securite import chiffrement

    client.put(f"/ecoles/{ecole.id}/helloasso", json=CLES)
    monkeypatch.setattr(chiffrement, "_secret", lambda: b"un autre serveur")
    reponse = client.post(f"/ecoles/{ecole.id}/helloasso/retester")
    assert reponse.status_code == 422 and "changez les clés" in reponse.json()["detail"]


@pytest.mark.rbac_reel
def test_reserve_a_l_administrateur_principal(client, db_session, ecole, helloasso):
    # Le premier admin de l'école en est l'Administrateur principal.
    proprietaire = Comptes().create(db_session, ecole_id=ecole.id, role="admin", nom="Noir", prenom="Léo")
    admin = Comptes().create(db_session, ecole_id=ecole.id, role="admin", nom="Blanc", prenom="Ima")
    assert client.get(f"/ecoles/{ecole.id}/helloasso", headers=entetes_session(admin)).status_code == 403
    assert client.get(f"/ecoles/{ecole.id}/helloasso", headers=entetes_session(proprietaire)).status_code == 200


def test_connexion_par_l_api(monkeypatch):
    """Les appels à HelloAsso : jeton, association, formulaires d'adhésion."""
    from helloasso import api

    class Reponse:
        def __init__(self, status, corps):
            self.status_code, self.ok, self._corps = status, status < 400, corps

        def json(self):
            return self._corps

    def post(url, data, timeout):
        assert url == "https://api.helloasso.com/oauth2/token" and data["grant_type"] == "client_credentials"
        return Reponse(200, {"access_token": "jeton"}) if data["client_secret"] == "bon" else Reponse(400, {})

    def get(url, headers, params, timeout):
        assert headers == {"Authorization": "Bearer jeton"}
        if url.endswith("/v5/users/me/organizations"):
            return Reponse(200, [{"name": "Alliance Sambo", "organizationSlug": "alliance-sambo"}])
        assert url.endswith("/v5/organizations/alliance-sambo/forms") and params["formTypes"] == "Membership"
        return Reponse(200, {"data": [{"title": "Adhésion 2026-2027", "formSlug": "adhesion"}]})

    monkeypatch.setattr(api.requests, "post", post)
    monkeypatch.setattr(api.requests, "get", get)
    assert api.connect("id", "bon") == api.Organization("Alliance Sambo", "alliance-sambo", ["Adhésion 2026-2027"])
    with pytest.raises(api.HelloAssoError, match="refuse ces clés"):
        api.connect("id", "mauvais")
