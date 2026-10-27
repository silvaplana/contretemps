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


# --- Étape 8b : la campagne de la saison et ses champs (spec §3) ---

QUESTIONS = {
    "adhesion": [
        {"source_key": "11", "label": "Genre (H/F)", "required": True, "format": "list", "choices": ["H", "F"]},
        {"source_key": "12", "label": "Date de naissance", "required": True, "format": "date", "choices": None},
    ],
    "stage": [
        {"source_key": "12", "label": "Date de naissance", "required": False, "format": "date", "choices": None},
    ],
}


@pytest.fixture()
def campagnes(monkeypatch, helloasso):
    from app import main
    from helloasso.api import Form

    campaigns = main.core.helloasso_campaigns
    monkeypatch.setattr(campaigns, "forms", lambda client_id, secret, slug: [
        Form("Membership", "adhesion", "Adhésion 2026-2027", "Public"),
        Form("Event", "stage", "Stage d'été", "Private"),
    ])
    monkeypatch.setattr(
        campaigns, "form_fields", lambda client_id, secret, slug, form_type, form_slug: QUESTIONS[form_slug]
    )


def _champs(client, ecole):
    return {c["label"]: c for c in client.get(f"/ecoles/{ecole.id}/champs").json()}


def test_campagne_impose_ses_champs(client, db_session, ecole, campagnes):
    url = f"/ecoles/{ecole.id}/helloasso/campagne"
    assert client.get(url).json()["connected"] is False
    client.put(f"/ecoles/{ecole.id}/helloasso", json=CLES)
    etat = client.get(url).json()
    assert etat["form"] is None and [f["name"] for f in etat["forms"]] == ["Adhésion 2026-2027", "Stage d'été"]
    nos = client.post(f"/ecoles/{ecole.id}/champs", json={"label": "Taille de kimono", "format": "short_text"})

    etat = client.put(url, json={"form_type": "Membership", "form_slug": "adhesion"}).json()
    assert etat["form"]["name"] == "Adhésion 2026-2027"
    champs = _champs(client, ecole)
    genre = champs["Genre (H/F)"]
    assert (genre["source"], genre["format"], genre["choices"], genre["required"]) == (
        "helloasso", "list", ["H", "F"], True,
    )
    # En tête de la fiche ; les nôtres restent.
    ordre = list(champs)
    assert ordre.index("Genre (H/F)") < ordre.index("Taille de kimono")

    # Verrouillé : seuls les réglages avancés changent ; ne se retire pas.
    refus = client.patch(f"/champs/{genre['id']}", json={"label": "Sexe"})
    assert refus.status_code == 422 and "réglages avancés" in refus.json()["detail"]
    assert client.patch(f"/champs/{genre['id']}", json={"member_sees": False}).status_code == 200
    assert client.delete(f"/champs/{genre['id']}").status_code == 422
    assert client.patch(f"/champs/{nos.json()['id']}", json={"label": "Taille"}).status_code == 200

    # Changer de campagne : la date de naissance (même question) reste, le
    # genre quitte la fiche.
    naissance = champs["Date de naissance"]["id"]
    client.put(url, json={"form_type": "Event", "form_slug": "stage"})
    champs = _champs(client, ecole)
    assert "Genre (H/F)" not in champs and champs["Date de naissance"]["id"] == naissance
    assert champs["Date de naissance"]["required"] is False

    # « Nos champs » : plus de campagne, les nôtres restent.
    assert client.delete(url).status_code == 204
    champs = _champs(client, ecole)
    assert not any(c["source"] for c in champs.values()) and "Taille" in champs
    assert client.get(url).json()["form"] is None


def test_campagne_inconnue_ou_helloasso_muet(client, db_session, ecole, campagnes, monkeypatch):
    from app import main
    from helloasso.api import HelloAssoError

    client.put(f"/ecoles/{ecole.id}/helloasso", json=CLES)
    url = f"/ecoles/{ecole.id}/helloasso/campagne"
    refus = client.put(url, json={"form_type": "Membership", "form_slug": "disparue"})
    assert refus.status_code == 422 and "n’existe plus" in refus.json()["detail"]
    client.put(url, json={"form_type": "Membership", "form_slug": "adhesion"})

    def muet(*_):
        raise HelloAssoError("HelloAsso ne répond pas : réessayez dans un moment.")

    monkeypatch.setattr(main.core.helloasso_campaigns, "forms", muet)
    etat = client.get(url).json()
    assert etat["form"]["name"] == "Adhésion 2026-2027" and "ne répond pas" in etat["error"]


def test_questions_du_formulaire(monkeypatch):
    from helloasso import api

    monkeypatch.setattr(api, "_token", lambda *_: "jeton")
    question = {"id": 7, "label": "Genre", "type": "ChoiceList", "isRequired": True, "values": ["H", "F"]}
    formulaire = {"tiers": [
        {"customFields": [question, {"id": 8, "label": "Photo", "type": "File"}]},
        {"customFields": [question, {"id": 9, "label": "Club précédent", "type": "Inconnu"}]},
    ]}

    def get(path, token, params=None):
        assert path == "/v5/organizations/alliance-sambo/forms/Membership/adhesion/public"
        return formulaire

    monkeypatch.setattr(api, "_get", get)
    champs = api.form_fields("id", "secret", "alliance-sambo", "Membership", "adhesion")
    assert [(c["source_key"], c["format"], c["required"]) for c in champs] == [
        ("7", "list", True), ("8", "file", False), ("9", "short_text", False),
    ]
