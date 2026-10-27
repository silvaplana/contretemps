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


# --- Étape 8c : la synchronisation (spec §4) ---


def _inscrit(item_id, prenom, nom, payeur, reponses=(), state="Processed", montant=12000):
    return {
        "item_id": item_id, "order_id": f"c{item_id}", "first_name": prenom, "last_name": nom,
        "payer_email": payeur, "tier_name": "Adulte", "amount": montant, "discount_code": None,
        "state": state, "order_date": "2026-09-02T10:00:00", "answers": list(reponses),
        "payments": [{"amount": montant, "date": "2026-09-02T10:00:00", "state": "Authorized", "means": "Card",
                      "installment": 1}],
    }


def test_synchroniser_les_inscrits(client, db_session, ecole, campagnes, monkeypatch):
    from app import main
    from comptes import Compte, Comptes
    from eleves import Eleves
    from helloasso import HelloAssoRegistration
    from members import values

    client.put(f"/ecoles/{ecole.id}/helloasso", json=CLES)
    url = f"/ecoles/{ecole.id}/helloasso/synchroniser"
    refus = client.post(url)
    assert refus.status_code == 422 and "campagne" in refus.json()["detail"]
    client.put(f"/ecoles/{ecole.id}/helloasso/campagne", json={"form_type": "Membership", "form_slug": "adhesion"})

    leon, _ = Eleves(Comptes()).create(db_session, ecole.id, nom="Perrin", prenom="Léon", email="leon@test.fr")
    prof = Comptes().create(db_session, ecole_id=ecole.id, role="professeur", nom="Noir", prenom="Ana")
    genre = [{"id": "11", "name": "Genre (H/F)", "answer": "F"}]
    inscrits = [
        _inscrit("1", "Léa", "Martin", "parent@test.fr", [*genre, {"id": "12", "name": "Date", "answer": "05/11/0017"}]),
        _inscrit("2", "Tom", "Martin", "parent@test.fr"),
        _inscrit("3", "Leon", "PERRIN", "leon@test.fr"),
        _inscrit("4", "Ana", "Noir", "ana@test.fr"),
        _inscrit("5", "Zoé", "Annulée", "z@test.fr", state="Refunded"),
    ]
    monkeypatch.setattr(main.core.helloasso_sync, "orders", lambda *_: inscrits)

    assert client.post(url).json() == {"created": 2, "completed": 2, "updated": 0, "gone": 0}
    lignes = {r.item_id: r for r in db_session.query(HelloAssoRegistration)}
    assert set(lignes) == {"1", "2", "3", "4"} and lignes["3"].member_id == leon.id
    assert lignes["4"].member_id == prof.id and lignes["1"].payments[0]["means"] == "Card"
    lea = db_session.get(Compte, lignes["1"].member_id)
    tom = db_session.get(Compte, lignes["2"].member_id)
    assert (lea.nom, lea.prenom, lea.payeur) == ("Martin", "Léa", "parent@test.fr")
    assert lea.famille_id is not None and lea.famille_id == tom.famille_id
    reponses = {(r["field"].label, r["field"].source): r["value"] for r in values.answers(db_session, lea)}
    assert reponses[("Genre (H/F)", "helloasso")] == "F"
    assert reponses[("Date de naissance", "helloasso")] == "2017-11-05"
    # Notre date de naissance (cachée) la reçoit aussi : elle donne l’âge.
    assert values.known_of(db_session, lea)["birth_date"] == "2017-11-05"
    assert db_session.query(Compte).filter(Compte.nom == "Annulée").count() == 0

    # Deuxième passage : Tom n'est plus sur HelloAsso, rien n'est recréé.
    inscrits.pop(1)
    assert client.post(url).json() == {"created": 0, "completed": 0, "updated": 3, "gone": 1}
    db_session.expire_all()
    assert db_session.get(HelloAssoRegistration, lignes["2"].id).gone_at is not None
    assert db_session.get(Compte, tom.id) is not None
    assert client.get(f"/ecoles/{ecole.id}/helloasso/campagne").json()["synced_at"] is not None


def test_reponses_helloasso():
    from datetime import date

    from helloasso.sync import answer_value, fix_short_year

    assert fix_short_year(85, today=date(2026, 10, 27)) == 1985 and fix_short_year(17) == 2017
    assert answer_value("date", "5/11/2012") == "2012-11-05"
    assert answer_value("date", "2012-11-05T00:00:00") == "2012-11-05"
    assert answer_value("yes_no", "Oui") is True and answer_value("number", "1,5") == 1.5
    assert answer_value("short_text", "") is None and answer_value("list", " H ") == "H"


def test_commandes_par_l_api(monkeypatch):
    from helloasso import api

    monkeypatch.setattr(api, "_token", lambda *_: "jeton")
    pages = {
        1: {"data": [{
            "id": 900, "date": "2026-09-02", "payer": {"email": "parent@test.fr", "firstName": "Paul"},
            "payments": [{"id": 1, "date": "2026-09-02", "state": "Authorized", "paymentMeans": "Card",
                          "installmentNumber": 1}],
            "items": [
                {"id": 7, "type": "Membership", "name": "Enfant", "amount": 9000, "state": "Processed",
                 "user": {"firstName": "Léa", "lastName": "Martin"}, "discount": {"code": "FRATRIE"},
                 "customFields": [{"id": 11, "name": "Genre", "answer": "F"}],
                 "payments": [{"id": 1, "shareAmount": 9000}]},
                {"id": 8, "type": "Donation", "amount": 500},
            ],
        }], "pagination": {"totalPages": 2}},
        2: {"data": [{"id": 901, "payer": {"email": "x@test.fr", "firstName": "Ana", "lastName": "Noir"},
                      "items": [{"id": 9, "type": "Registration", "amount": 0}]}],
            "pagination": {"totalPages": 2}},
    }

    def get(path, token, params=None):
        assert path == "/v5/organizations/alliance/forms/Membership/adhesion/orders"
        return pages[params["pageIndex"]]

    monkeypatch.setattr(api, "_get", get)
    inscrits = api.orders("id", "secret", "alliance", "Membership", "adhesion")
    assert [(i["item_id"], i["first_name"], i["last_name"]) for i in inscrits] == [
        ("7", "Léa", "Martin"), ("9", "Ana", "Noir"),
    ]
    assert inscrits[0]["discount_code"] == "FRATRIE" and inscrits[0]["answers"] == [
        {"id": "11", "name": "Genre", "answer": "F"},
    ]
    assert inscrits[0]["payments"] == [
        {"amount": 9000, "date": "2026-09-02", "state": "Authorized", "means": "Card", "installment": 1},
    ]
