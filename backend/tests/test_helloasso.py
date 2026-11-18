"""Module HelloAsso, étape 8a : la connexion (spec/modules/helloasso.md §2).
Aucun appel réseau : `Connection.connect` est remplacé."""

import pytest
from comptes import Comptes
from conftest import entetes_session
from ecoles import Ecoles

CLES = {"client_id": "3f9c2a", "client_secret": "le-secret"}


@pytest.fixture()
def ecole(db_session):
    from app.modules import MODULES
    from registry.activation import set_enabled

    ecole = Ecoles().create(db_session, nom="Sambo La Ciotat", code_postal="13600")
    # HelloAsso est éteint par défaut (Seb, 18/11) : l'école l'allume.
    set_enabled(db_session, ecole.id, MODULES, "helloasso", True)
    return ecole


@pytest.fixture(autouse=True)
def _acces_au_financier(monkeypatch):
    """Les droits sont neutralisés (conftest.py) : l'appelant a l'accès au
    Financier, sauf quand un test le retire."""
    from comptes import roles

    monkeypatch.setattr(roles, "has_right", lambda compte, droit: True)


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


def test_formulaires_adhesion_et_evenement(monkeypatch):
    """La liste des campagnes : sans le filtre « Membership,Event » en un
    seul paramètre (liste vide à ASC, Seb 18/11) ; on lit tout et on garde
    les adhésions et les événements."""
    from helloasso import api

    class Reponse:
        def __init__(self, status, corps):
            self.status_code, self.ok, self._corps = status, status < 400, corps

        def json(self):
            return self._corps

    def get(url, headers, params, timeout):
        if "," in str((params or {}).get("formTypes", "")):
            return Reponse(400, {})
        return Reponse(200, {"data": [
            {"title": "Adhésion 2026-2027", "formSlug": "adhesion-2026-2027", "formType": "Membership", "state": "Public"},
            {"title": "Stage d'été", "formSlug": "stage", "formType": "Event", "state": "Public"},
            {"title": "Dons", "formSlug": "dons", "formType": "Donation", "state": "Public"},
        ]})

    monkeypatch.setattr(api, "_token", lambda *_: "jeton")
    monkeypatch.setattr(api.requests, "get", get)
    assert [(f.form_type, f.form_slug) for f in api.forms("id", "secret", "asc")] == [
        ("Membership", "adhesion-2026-2027"), ("Event", "stage"),
    ]


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

    assert client.post(url).json() == {"created": 3, "completed": 2, "updated": 0, "gone": 0}
    lignes = {r.item_id: r for r in db_session.query(HelloAssoRegistration)}
    assert set(lignes) == {"1", "2", "3", "4", "5"} and lignes["3"].member_id == leon.id
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
    # Remboursée : recopiée avec son état, jamais ignorée (spec §7.1).
    assert lignes["5"].state == "Refunded" and db_session.get(Compte, lignes["5"].member_id).nom == "Annulée"

    # Deuxième passage : Tom n'est plus sur HelloAsso, rien n'est recréé.
    inscrits.pop(1)
    assert client.post(url).json() == {"created": 0, "completed": 0, "updated": 4, "gone": 1}
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
                          "installmentNumber": 1, "cashOutState": "CashedOut", "cashOutDate": "2026-10-07"}],
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
        {"id": "11", "name": "Genre", "type": "", "answer": "F"},
    ]
    assert inscrits[0]["payer_name"] == "Paul" and inscrits[1]["payer_name"] == "Ana Noir"
    assert inscrits[0]["payments"] == [
        {"amount": 9000, "date": "2026-09-02", "state": "Authorized", "means": "Card", "installment": 1,
         "cash_out_state": "CashedOut", "cash_out_date": "2026-10-07"},
    ]


# --- Étape 8d : les tarifs HelloAsso en lecture seule (spec §3, core.md §9.3) ---


def test_tarifs_de_la_campagne(client, db_session, ecole, campagnes, monkeypatch):
    from app import main

    url = f"/ecoles/{ecole.id}/helloasso/tarifs"
    assert client.get(url).json()["campaign"] is False
    client.put(f"/ecoles/{ecole.id}/helloasso", json=CLES)
    client.put(f"/ecoles/{ecole.id}/helloasso/campagne", json={"form_type": "Membership", "form_slug": "adhesion"})
    prix = {
        "plans": [{"name": "Adulte", "price": 29000, "min_amount": None, "description": "", "frequency": ""}],
        "options": [{"name": "Kimono", "price": 4500, "required": False}],
    }
    monkeypatch.setattr(main.core.helloasso_campaigns, "form_prices", lambda *_: prix)
    inscrits = [
        {**_inscrit("1", "Léa", "Martin", "p@test.fr"), "discount_code": "RENOUV"},
        {**_inscrit("2", "Tom", "Martin", "p@test.fr"), "discount_code": "RENOUV"},
        _inscrit("3", "Ana", "Noir", "a@test.fr"),
    ]
    monkeypatch.setattr(main.core.helloasso_sync, "orders", lambda *_: inscrits)
    client.post(f"/ecoles/{ecole.id}/helloasso/synchroniser")

    tarifs = client.get(url).json()
    assert tarifs["campaign"] is True and tarifs["form_name"] == "Adhésion 2026-2027"
    assert tarifs["plans"][0]["price"] == 29000 and tarifs["options"][0]["name"] == "Kimono"
    assert tarifs["codes"] == [{"code": "RENOUV", "uses": 2}]

    def muet(*_):
        from helloasso.api import HelloAssoError

        raise HelloAssoError("HelloAsso ne répond pas : réessayez dans un moment.")

    monkeypatch.setattr(main.core.helloasso_campaigns, "form_prices", muet)
    tarifs = client.get(url).json()
    assert tarifs["form_name"] == "Adhésion 2026-2027" and "ne répond pas" in tarifs["error"]


def test_formules_par_l_api(monkeypatch):
    from helloasso import api

    monkeypatch.setattr(api, "_token", lambda *_: "jeton")
    kimono = {"label": "Kimono", "price": 4500, "isRequired": False}
    formulaire = {"tiers": [
        {"label": "Solo, en 3 fois", "price": 30000, "tierType": "Membership", "paymentFrequency": "Installment",
         "extraOptions": [kimono]},
        {"label": "Prix libre", "price": None, "minAmount": 1000, "tierType": "Membership", "extraOptions": [kimono]},
        {"label": "Don", "tierType": "Donation"},
    ]}
    monkeypatch.setattr(api, "_get", lambda path, token, params=None: formulaire)
    prix = api.form_prices("id", "secret", "alliance", "Membership", "adhesion")
    assert [(p["name"], p["price"], p["min_amount"], p["frequency"]) for p in prix["plans"]] == [
        ("Solo, en 3 fois", 30000, None, "En plusieurs fois"), ("Prix libre", None, 1000, ""),
    ]
    assert prix["options"] == [{"name": "Kimono", "price": 4500, "required": False}]


# --- Étape 5 : adhérents entièrement imposés par HelloAsso (spec §7) ---

PHOTO_URL = "https://docs.helloasso.com/customFieldsAnswer/4242"
CERTIFICAT_URL = "https://docs.helloasso.com/customFieldsAnswer/4343"


def _saison_imposee(client, ecole, monkeypatch, inscrits):
    from app import main

    client.put(f"/ecoles/{ecole.id}/helloasso", json=CLES)
    client.put(f"/ecoles/{ecole.id}/helloasso/campagne", json={"form_type": "Membership", "form_slug": "adhesion"})
    monkeypatch.setattr(main.core.helloasso_sync, "orders", lambda *_: inscrits)
    return client.post(f"/ecoles/{ecole.id}/helloasso/synchroniser").json()


def test_saison_imposee_sans_fiche_a_la_main(client, db_session, ecole, campagnes, monkeypatch):
    """Totalement esclave (spec §7.1) : ni création, ni import, ni
    suppression d'une fiche d'élève, refusés par le serveur ; la
    synchronisation, elle, crée les fiches. « Nos champs » ou le module
    éteint rouvrent tout."""
    from app import main
    from registry import activation

    params = {"ecole_id": ecole.id}
    avant = client.post("/eleves", params=params, json={"nom": "Avant", "prenom": "Léon"})
    assert avant.status_code == 201
    assert _saison_imposee(client, ecole, monkeypatch, [_inscrit("1", "Léa", "Martin", "p@test.fr")])["created"] == 1

    refus = client.post("/eleves", params=params, json={"nom": "Perrin", "prenom": "Léon"})
    assert refus.status_code == 409 and "HelloAsso" in refus.json()["detail"]
    assert client.delete(f"/eleves/{avant.json()['id']}").status_code == 409
    fichier = ("eleves.csv", b"Nom;Prenom\nPerrin;Leon\n", "text/csv")
    assert client.post("/eleves/import/previsualiser", params=params, files={"fichier": fichier}).status_code == 409
    assert client.post("/eleves/import/valider", params=params, json={"lignes": []}).status_code == 409
    # L'assistant non plus.
    with pytest.raises(ValueError, match="HelloAsso"):
        main.core.eleves_client.create(db_session, ecole.id, nom="Perrin", prenom="Léon")

    # FFST a besoin de HelloAsso : on l'éteint d'abord.
    activation.set_enabled(db_session, ecole.id, main.MODULES, "ffst", False)
    activation.set_enabled(db_session, ecole.id, main.MODULES, "helloasso", False)
    assert client.post("/eleves", params=params, json={"nom": "Perrin", "prenom": "Léon"}).status_code == 201
    activation.set_enabled(db_session, ecole.id, main.MODULES, "helloasso", True)
    assert client.post("/eleves", params=params, json={"nom": "Perrin", "prenom": "Zoé"}).status_code == 409
    client.delete(f"/ecoles/{ecole.id}/helloasso/campagne")
    assert client.post("/eleves", params=params, json={"nom": "Perrin", "prenom": "Zoé"}).status_code == 201


def test_ecole_sans_helloasso_inchangee(client, db_session, ecole, campagnes):
    """Contretemps, Le Beausset : sans campagne, rien ne change."""
    params = {"ecole_id": ecole.id}
    creee = client.post("/eleves", params=params, json={"nom": "Perrin", "prenom": "Léon"})
    assert creee.status_code == 201
    assert client.delete(f"/eleves/{creee.json()['id']}").status_code == 204
    assert client.get(f"/ecoles/{ecole.id}/helloasso/adherents").json() == {
        "imposed": False, "form_name": None, "can_refresh": False, "can_cancel": False, "checks_on": False,
        "members": {},
    }


def _image(couleur=(200, 30, 30), taille=(60, 40)):
    import io

    from PIL import Image

    tampon = io.BytesIO()
    Image.new("RGB", taille, couleur).save(tampon, format="PNG")
    return tampon.getvalue()


def test_tableau_et_fiche_des_adherents(client, db_session, ecole, campagnes, monkeypatch, tmp_path):
    """Colonnes Montant, Code promo, Photo, Statut HelloAsso (spec §7.2) et
    la fiche (§7.3) ; la photo et les documents relayés depuis HelloAsso,
    seule la vignette est gardée."""
    import io

    from app import main
    from comptes import Compte
    from helloasso import members
    from PIL import Image

    monkeypatch.setattr(members, "PHOTOS_DIR", tmp_path)
    fichiers = [
        {"id": "20", "name": "photo d'identité", "type": "File", "answer": PHOTO_URL},
        {"id": "21", "name": "Certificat médical", "type": "File", "answer": CERTIFICAT_URL},
        {"id": "22", "name": "Ville", "type": "TextInput", "answer": "La Ciotat"},
    ]
    lea = {**_inscrit("1", "Léa", "Martin", "p@test.fr", fichiers, montant=16000), "discount_code": "FRATRIE",
           "payer_name": "Claire Martin"}
    resiliee = _inscrit("2", "Inès", "Navarro", "i@test.fr", state="Canceled")
    _saison_imposee(client, ecole, monkeypatch, [lea, resiliee])

    tableau = client.get(f"/ecoles/{ecole.id}/helloasso/adherents").json()
    assert tableau["imposed"] is True and tableau["can_refresh"] is True
    lignes = {db_session.get(Compte, int(i)).prenom: ligne for i, ligne in tableau["members"].items()}
    assert lignes["Léa"] == {"rank": 0, "amount": 16000, "discount_code": "FRATRIE", "state": "Processed",
                             "cancelled": False, "photo": True, "mails": 0, "sms": 0, "has_phone": False,
                             "check": None}
    assert lignes["Inès"]["cancelled"] is True and lignes["Inès"]["photo"] is False

    lea_id = next(int(i) for i, ligne in tableau["members"].items() if ligne["photo"])
    fiche = client.get(f"/ecoles/{ecole.id}/helloasso/adherents/{lea_id}").json()
    assert fiche["files"] == [{"index": 0, "name": "photo d'identité"}, {"index": 1, "name": "Certificat médical"}]
    assert fiche["answers"] == [{"name": "Ville", "answer": "La Ciotat"}]
    assert (fiche["payer_name"], fiche["tier_name"], fiche["payments"][0]["means"]) == ("Claire Martin", "Adulte", "Card")

    lus = []

    def fetch_file(client_id, secret, url):
        lus.append(url)
        return (_image(), "image/png") if url == PHOTO_URL else (b"%PDF-certificat", "application/pdf")

    monkeypatch.setattr(main.core.helloasso_receiver, "fetch_file", fetch_file, raising=False)
    photo = client.get(f"/ecoles/{ecole.id}/helloasso/adherents/{lea_id}/photo", params={"size": 64})
    assert photo.status_code == 200 and photo.headers["content-type"] == "image/jpeg"
    assert Image.open(io.BytesIO(photo.content)).size == (64, 64)
    # Vignette gardée : HelloAsso n'est plus appelé.
    client.get(f"/ecoles/{ecole.id}/helloasso/adherents/{lea_id}/photo", params={"size": 64})
    assert lus == [PHOTO_URL]

    certificat = client.get(f"/ecoles/{ecole.id}/helloasso/adherents/{lea_id}/fichiers/1")
    assert certificat.content == b"%PDF-certificat" and certificat.headers["cache-control"] == "no-store"
    assert list(tmp_path.rglob("*")) and not any("4343" in p.name for p in tmp_path.rglob("*"))
    assert client.get(f"/ecoles/{ecole.id}/helloasso/adherents/{lea_id}/fichiers/2").status_code == 404
    autre = client.get(f"/ecoles/{ecole.id}/helloasso/adherents/999999")
    assert autre.status_code == 404


def test_vignette_d_un_pdf():
    """Un PDF déposé à la place d'une photo donne sa première page."""
    import io

    import pymupdf
    from helloasso.members import is_file_url, photo_index, thumbnail
    from PIL import Image

    with pymupdf.open() as pdf:
        pdf.new_page(width=200, height=300)
        contenu = pdf.tobytes()
    assert Image.open(io.BytesIO(thumbnail(contenu, 128))).size == (128, 128)
    assert is_file_url(PHOTO_URL) and not is_file_url("https://evil.test/customFieldsAnswer/1")
    assert not is_file_url("https://docs.helloasso.com/autre/1")
    assert photo_index([{"name": "Photo d’identité", "answer": PHOTO_URL}]) == 0
    assert photo_index([{"name": "Certificat", "answer": PHOTO_URL}]) is None


# --- Étape 11 : le choix de la saison (spec §8) ---


def test_choix_de_la_saison(client, db_session, ecole, campagnes, monkeypatch):
    """HelloAsso fait tout (la campagne) / L'appli fait tout, HelloAsso
    encaisse / Sans HelloAsso. Le choix 2 n'impose rien : fiches libres."""
    url = f"/ecoles/{ecole.id}/helloasso/saison"
    assert client.get(url).json()["connected"] is False
    client.put(f"/ecoles/{ecole.id}/helloasso", json=CLES)
    lu = client.get(url).json()
    assert (lu["mode"], lu["can_change"], lu["form"]) == ("none", True, None)

    _saison_imposee(client, ecole, monkeypatch, [_inscrit("1", "Léa", "Martin", "p@test.fr")])
    lu = client.get(url).json()
    assert lu["mode"] == "master" and lu["form"]["name"] == "Adhésion 2026-2027"
    assert len([c for c in _champs(client, ecole).values() if c["source"] == "helloasso"]) > 0

    lu = client.put(url, json={"mode": "payment"}).json()
    assert lu["mode"] == "payment" and lu["form"] is None
    # La campagne est retirée : ses champs quittent la fiche, plus de verrou.
    assert not [c for c in _champs(client, ecole).values() if c["source"] == "helloasso"]
    assert client.get(f"/ecoles/{ecole.id}/helloasso/adherents").json()["imposed"] is False
    assert client.get(f"/ecoles/{ecole.id}/helloasso/campagne").json()["form"] is None
    assert client.post("/eleves", params={"ecole_id": ecole.id}, json={"nom": "A", "prenom": "B"}).status_code == 201
    # « Nos champs » ne touche pas au choix 2 ; la synchronisation non plus.
    client.delete(f"/ecoles/{ecole.id}/helloasso/campagne")
    assert client.get(url).json()["mode"] == "payment"
    assert client.post(f"/ecoles/{ecole.id}/helloasso/synchroniser").status_code == 422

    # Rechoisir une campagne repasse en « HelloAsso fait tout ».
    client.put(f"/ecoles/{ecole.id}/helloasso/campagne", json={"form_type": "Membership", "form_slug": "adhesion"})
    assert client.get(url).json()["mode"] == "master"
    assert client.put(url, json={"mode": "none"}).json()["mode"] == "none"
    assert client.put(url, json={"mode": "autre"}).status_code == 422


def test_impayes_helloasso(client, db_session, ecole, campagnes, monkeypatch):
    """Admin > Impayés HelloAsso (spec §7.4) : les adhésions avec au moins
    une échéance refusée ou en échec ; une échéance à venir ne compte pas."""
    def echeance(montant, etat, date):
        return {"amount": montant, "date": date, "state": etat, "means": "Card", "installment": 1}

    payee = _inscrit("1", "Léa", "Martin", "p@test.fr")
    refusee = {**_inscrit("2", "Tom", "Benali", "t@test.fr", montant=24000), "payments": [
        echeance(8000, "Authorized", "2026-09-02T10:00:00"),
        echeance(8000, "Refused", "2026-10-02T10:00:00"),
        echeance(8000, "Error", "2026-11-02T10:00:00"),
    ]}
    a_venir = {**_inscrit("3", "Inès", "Navarro", "i@test.fr", montant=24000), "payments": [
        echeance(8000, "Authorized", "2026-09-02T10:00:00"),
        echeance(8000, "Pending", "2026-12-02T10:00:00"),
    ]}
    url = f"/ecoles/{ecole.id}/helloasso/impayes"
    assert client.get(url).json() == {"campaign": False, "members": [], "upcoming": []}
    _saison_imposee(client, ecole, monkeypatch, [payee, refusee, a_venir])

    impayes = client.get(url).json()
    assert impayes["campaign"] is True
    assert [(m["last_name"], m["first_name"], m["email"], m["total"], m["unpaid"]) for m in impayes["members"]] == [
        ("Benali", "Tom", "t@test.fr", 24000, 16000),
    ]
    assert [p["date"][:10] for p in impayes["members"][0]["refused"]] == ["2026-10-02", "2026-11-02"]
    assert impayes["members"][0]["member_id"] is not None


# --- Étape 8 : contact et résiliation (spec §7.6, §7.7) ---


def test_mail_sms_et_messages_preenregistres(client, db_session, ecole, campagnes, monkeypatch):
    from app import main
    from comptes import Compte, roles

    monkeypatch.setattr(roles, "has_right", lambda compte, droit: True)
    telephone = {"id": "30", "name": "Numéro de téléphone", "type": "Phone", "answer": "06 12 34 56 78"}
    _saison_imposee(client, ecole, monkeypatch, [
        _inscrit("1", "Léa", "Martin", "parent@test.fr", [telephone]),
        _inscrit("2", "Tom", "Noir", "tom@test.fr"),
    ])
    fiches = {db_session.get(Compte, int(i)).prenom: int(i)
              for i in client.get(f"/ecoles/{ecole.id}/helloasso/adherents").json()["members"]}
    lea, tom = fiches["Léa"], fiches["Tom"]
    envoyes = []

    def envoyer(db, org_id, a, sujet, texte, html):
        envoyes.append((org_id, a, sujet, texte))
        return "contact@club.fr"

    monkeypatch.setattr(main.core.helloasso_receiver, "send_mail", envoyer)
    url = f"/ecoles/{ecole.id}/helloasso/adherents"
    reponse = client.post(f"{url}/{lea}/mail", json={"subject": "Certificat", "message": "Bonjour Léa,\n\nMerci."})
    assert reponse.json() == {"to": "parent@test.fr", "cc": "contact@club.fr"}
    assert envoyes == [(ecole.id, "parent@test.fr", "Certificat", "Bonjour Léa,\n\nMerci.")]
    assert client.post(f"{url}/{lea}/mail", json={"subject": "", "message": "x"}).status_code == 422

    def panne(*_):
        raise RuntimeError("SMTP indisponible")

    monkeypatch.setattr(main.core.helloasso_receiver, "send_mail", panne)
    echec = client.post(f"{url}/{lea}/mail", json={"subject": "Relance", "message": "Bonjour"})
    assert echec.status_code == 502 and "SMTP indisponible" in echec.json()["detail"]

    assert client.post(f"{url}/{lea}/sms", json={"message": "Bonjour Léa"}).json() == {"phone": "+33612345678"}
    assert client.post(f"{url}/{tom}/sms", json={"message": "Bonjour"}).status_code == 422

    lignes = client.get(url).json()["members"]
    assert (lignes[str(lea)]["mails"], lignes[str(lea)]["sms"], lignes[str(lea)]["has_phone"]) == (1, 1, True)
    assert (lignes[str(tom)]["mails"], lignes[str(tom)]["has_phone"]) == (0, False)
    fiche = client.get(f"{url}/{lea}").json()
    assert [(m["kind"], m["sent"]) for m in fiche["messages"]] == [("sms", True), ("mail", False), ("mail", True)]

    route = f"/ecoles/{ecole.id}/helloasso/messages"
    client.post(route, json={"kind": "mail", "subject": "Certificat", "body": "Bonjour {prénom}"})
    client.post(route, json={"kind": "mail", "subject": "Certificat", "body": "Bonjour {prénom}"})
    gardes = client.post(route, json={"kind": "sms", "body": "Bonjour {prénom}"}).json()
    assert [t["body"] for t in gardes] == ["Bonjour {prénom}"]
    mails = client.get(route, params={"kind": "mail"}).json()
    assert len(mails) == 1 and mails[0]["subject"] == "Certificat"
    assert client.delete(f"{route}/{mails[0]['id']}", params={"kind": "mail"}).json() == []


def test_resilier_une_commande(client, db_session, ecole, campagnes, monkeypatch):
    """Toute la commande (une fratrie) ; aperçu avant ; droit Accès au
    Financier ; HelloAsso n'est appelé qu'une fois, jamais pour une
    commande déjà résiliée."""
    from app import main
    from comptes import Compte, roles

    def echeances(montant):
        return [
            {"amount": montant // 3, "date": "2026-09-05T10:00:00", "state": "Authorized"},
            {"amount": montant // 3, "date": "2026-10-05T10:00:00", "state": "Pending"},
            {"amount": montant // 3, "date": "2026-11-05T10:00:00", "state": "Pending"},
        ]

    timeo = {**_inscrit("4", "Timéo", "Roux", "claire@test.fr", montant=15000), "order_id": "c504",
             "payments": echeances(15000)}
    lina = {**_inscrit("5", "Lina", "Roux", "claire@test.fr", montant=15000), "order_id": "c504",
            "payments": echeances(15000)}
    _saison_imposee(client, ecole, monkeypatch, [timeo, lina, _inscrit("6", "Hugo", "Ferrand", "h@test.fr")])
    fiches = {db_session.get(Compte, int(i)).prenom: int(i)
              for i in client.get(f"/ecoles/{ecole.id}/helloasso/adherents").json()["members"]}
    url = f"/ecoles/{ecole.id}/helloasso/adherents/{fiches['Timéo']}"

    monkeypatch.setattr(roles, "has_right", lambda compte, droit: False)
    assert client.get(f"{url}/resiliation").status_code == 403
    assert client.get(f"/ecoles/{ecole.id}/helloasso/adherents").json()["can_cancel"] is False
    monkeypatch.setattr(roles, "has_right", lambda compte, droit: True)

    apercu = client.get(f"{url}/resiliation").json()
    assert [m["first_name"] for m in apercu["members"]] == ["Timéo", "Lina"]
    assert (apercu["paid"], apercu["scheduled"], apercu["scheduled_count"], apercu["cancelled"]) == (
        10000, 20000, 4, False)

    appels = []
    monkeypatch.setattr(main.core.helloasso_receiver, "cancel_order", lambda *a: appels.append(a))
    assert client.post(f"{url}/resilier").json()["cancelled"] is True
    assert [a[-1] for a in appels] == ["c504"]
    lignes = client.get(f"/ecoles/{ecole.id}/helloasso/adherents").json()["members"]
    assert lignes[str(fiches["Lina"])]["cancelled"] is True and lignes[str(fiches["Hugo"])]["cancelled"] is False
    assert client.post(f"{url}/resilier").status_code == 409
    assert len(appels) == 1


class _Inspecteur:
    """Le modèle remplacé : rend `verdicts` et note ce qu'il a reçu."""

    def __init__(self, **verdicts):
        self.verdicts, self.appels = verdicts, []

    def inspect(self, club, answers, documents, today):
        from helloasso.checks import Verdict

        self.appels.append((club, answers["prenom"], sorted(documents)))
        resultats = {k: {"ok": True, "raison": ""} for k in ("photo", "certificat", "autorisation", "donnees")}
        resultats.update({k: {"ok": False, "raison": v} for k, v in self.verdicts.items()})
        return Verdict(results=resultats, cost=0.01)


def _dossier(naissance, certificat=True, autorisation=False):
    reponses = [
        {"id": "12", "name": "Date de naissance", "type": "Date", "answer": naissance},
        {"id": "20", "name": "photo d'identité", "type": "File", "answer": PHOTO_URL},
    ]
    if certificat:
        reponses.append({"id": "21", "name": "Certificat médical", "type": "File", "answer": CERTIFICAT_URL})
    if autorisation:
        reponses.append({"id": "23", "name": "Autorisation parentale", "type": "File", "answer": CERTIFICAT_URL})
    return reponses


@pytest.fixture()
def verificateur(monkeypatch):
    """Le vérificateur du module, sans fil d'exécution ni réseau."""
    from app import main

    checker = main.core.helloasso_checker
    monkeypatch.setattr(checker, "background", False)
    monkeypatch.setattr(checker.runs, "background", False)
    monkeypatch.setattr(checker, "fetch_file", lambda client_id, secret, url: (_image(), "image/png"))
    pousses, mails = [], []
    monkeypatch.setattr(checker, "push", lambda db, compte_id, titre, corps: pousses.append((compte_id, titre, corps)))
    monkeypatch.setattr(checker, "send_mail", lambda db, org_id, a, sujet, texte, html: mails.append((a, sujet, texte)))
    return checker, pousses, mails


def test_verification_d_un_dossier(db_session, ecole):
    """Contrôles sans modèle, puis un seul appel avec les documents (spec
    §7.5) ; l'autorisation parentale d'un majeur n'est pas regardée."""
    from datetime import date

    from helloasso import checks
    from helloasso.models import HelloAssoRegistration

    def inscription(item_id, reponses):
        r = HelloAssoRegistration(org_id=ecole.id, season_id=1, item_id=item_id, order_id="c", first_name="Léa",
                                  last_name="Martin", state="Processed", answers=reponses, payments=[])
        return r

    jour = date(2026, 11, 18)
    lire = lambda url: _image()  # noqa: E731
    bon = _Inspecteur()
    ok = checks.check(db_session, inscription("1", _dossier("14/03/1990", autorisation=True)), lire, bon, "Club", jour)
    assert (ok.status, ok.issues, ok.model) == ("ok", [], checks.MODEL)
    assert bon.appels == [("Club", "Léa", ["certificat", "photo"])]

    mineur = checks.check(db_session, inscription("2", _dossier("2016-01-09", certificat=False)), lire, bon, "Club", jour)
    assert mineur.status == "problem" and mineur.issues == [
        "Certificat médical manquant", "Autorisation parentale manquante (adhérent mineur)"]

    refus = _Inspecteur(certificat="Le certificat date de plus d'un an.")
    vieux = checks.check(db_session, inscription("3", _dossier("14/03/1990")), lire, refus, "Club", jour)
    assert vieux.issues == ["Certificat médical : Le certificat date de plus d'un an."]

    def illisible(url):
        return b"pas une image"

    sans = checks.check(db_session, inscription("4", _dossier("??")), illisible, bon, "Club", jour)
    assert sans.issues == ["Date de naissance absente ou illisible", "Photo d'identité : fichier illisible",
                           "Certificat médical : fichier illisible"]
    # Aucun document lisible : le modèle n'est pas appelé.
    assert len(bon.appels) == 2 and sans.cost == 0 and sans.model is None


def test_nouvel_adherent_verifie_et_signale(client, db_session, ecole, campagnes, monkeypatch, verificateur):
    """Éteints par défaut (spec §7.10) ; allumés : notification aux admins,
    dossier vérifié, mail à l'école s'il y a un problème."""
    from comptes import Comptes, roles
    from helloasso.models import HelloAssoCheck

    checker, pousses, mails = verificateur
    checker.inspector = _Inspecteur(photo="La photo ne montre personne.")
    monkeypatch.setattr(roles, "is_admin", lambda c: c.prenom == "Admin")
    ecole.email_contact = "contact@club.fr"
    admin = Comptes().create(db_session, ecole_id=ecole.id, role="admin", nom="Club", prenom="Admin")
    db_session.commit()
    inscrits = [_inscrit("1", "Léa", "Martin", "p@test.fr", _dossier("14/03/1990"))]
    _saison_imposee(client, ecole, monkeypatch, inscrits)
    assert pousses == [] and mails == [] and db_session.query(HelloAssoCheck).count() == 0

    reglages = f"/ecoles/{ecole.id}/helloasso/reglages"
    assert client.get(reglages).json() == {"check_files": False, "notify_new": False}
    client.put(reglages, json={"check_files": True, "notify_new": True})
    inscrits.append(_inscrit("2", "Noé", "Lefèvre", "n@test.fr", _dossier("11/10/2007")))
    client.post(f"/ecoles/{ecole.id}/helloasso/synchroniser")
    assert pousses == [(admin.id, "Nouvel adhérent", "Noé Lefèvre")]
    assert [(a, s) for a, s, _ in mails] == [("contact@club.fr", "Nouvel adhérent à vérifier : Noé Lefèvre")]
    assert "La photo ne montre personne." in mails[0][2]
    # Léa n'est pas nouvelle : ni vérifiée ni annoncée.
    assert [c.first_name for c in db_session.query(HelloAssoCheck)] == ["Noé"]


def test_verifier_les_adherents_et_valider(client, db_session, ecole, campagnes, monkeypatch, verificateur):
    """« Vérifier les adhérents » (Accès au Financier) relance ceux qui ne
    sont pas OK et envoie le rapport ; « Valider le dossier » et son
    Annuler ; colonne Vérification et fiche."""
    from comptes import Compte, roles

    checker, _, mails = verificateur
    ecole.email_contact = "contact@club.fr"
    db_session.commit()
    _saison_imposee(client, ecole, monkeypatch, [
        _inscrit("1", "Léa", "Martin", "p@test.fr", _dossier("14/03/1990")),
        _inscrit("2", "Noé", "Lefèvre", "n@test.fr", _dossier("11/10/2007", certificat=False)),
    ])
    url = f"/ecoles/{ecole.id}/helloasso/verification"
    assert client.post(url).status_code == 422  # éteinte
    client.put(f"/ecoles/{ecole.id}/helloasso/reglages", json={"check_files": True, "notify_new": False})
    assert client.get(url).json() == {"on": True, "running": False, "to_check": 2, "cost": 0.0, "can_run": True}

    checker.inspector = _Inspecteur()
    etat = client.post(url).json()
    assert (etat["to_check"], etat["running"], round(etat["cost"], 2)) == (1, False, 0.02)
    sujet, texte = mails[-1][1], mails[-1][2]
    assert sujet == "Sambo La Ciotat : vérification des dossiers" and "1 OK, 1 à regarder" in texte
    assert "Certificat médical manquant" in texte

    # Deuxième passage : Léa (OK) n'est plus revérifiée.
    checker.inspector = _Inspecteur()
    client.post(url)
    assert [a[1] for a in checker.inspector.appels] == ["Noé"]

    lignes = client.get(f"/ecoles/{ecole.id}/helloasso/adherents").json()
    assert lignes["checks_on"] is True
    par_prenom = {db_session.get(Compte, int(i)).prenom: (int(i), l["check"]) for i, l in lignes["members"].items()}
    noe, verdict = par_prenom["Noé"]
    assert verdict == {"ok": False, "issues": ["Certificat médical manquant"]}
    assert par_prenom["Léa"][1] == {"ok": True, "issues": []}
    adherent = f"/ecoles/{ecole.id}/helloasso/adherents/{noe}"
    assert client.post(f"{adherent}/valider").json() == {"ok": True, "issues": []}
    assert client.get(adherent).json()["check"] == {"ok": True, "issues": []}
    assert client.get(url).json()["to_check"] == 0
    assert client.delete(f"{adherent}/valider").json() == {"ok": False, "issues": ["Certificat médical manquant"]}

    monkeypatch.setattr(roles, "has_right", lambda compte, droit: False)
    assert client.post(url).status_code == 403


def test_argent_helloasso_pour_le_previsionnel(db_session, ecole):
    """Prévisionnel (financier.md §6.4) : des faits seulement, l'argent qui
    arrivera sur le compte après la date de départ ; rien si HelloAsso est
    éteint dans l'école."""
    from datetime import datetime

    from app.modules import MODULES
    from finances_contretemps.adapter import argent_helloasso
    from helloasso import money
    from helloasso.models import HelloAssoRegistration, SeasonHelloAsso
    from registry.activation import set_enabled

    db_session.add(SeasonHelloAsso(org_id=ecole.id, season_id=1, form_type="Membership", form_slug="a",
                                   form_name="Adhésions 2026-2027", synced_at=datetime(2026, 11, 18, 9)))

    def paiement(montant, jour, etat, versement=None, le=None, n=1):
        return {"amount": montant, "date": jour, "state": etat, "means": "Card", "installment": n,
                "cash_out_state": versement, "cash_out_date": le}

    def inscrit(item_id, paiements, state="Processed"):
        db_session.add(HelloAssoRegistration(org_id=ecole.id, season_id=1, item_id=item_id, order_id=item_id,
                                             first_name="A", last_name=item_id, state=state, payments=paiements))

    # En trois fois : la 1re versée avant le départ, deux échéances fixes.
    for i in ("1", "2"):
        inscrit(i, [paiement(9000, "2026-09-20", "Authorized", "CashedOut", "2026-10-10"),
                    paiement(9000, "2026-12-05T10:00:00", "Pending", n=2),
                    paiement(9000, "2027-02-05T10:00:00", "Pending", n=3)])
    # En une fois : encaissé, pas encore versé ; un autre versé après le départ.
    inscrit("3", [paiement(27000, "2026-11-12", "Authorized", "MoneyIn")])
    inscrit("4", [paiement(27000, "2026-10-30", "Authorized", "CashedOut", "2026-11-10")])
    # Un impayé et une adhésion résiliée : pas comptés.
    inscrit("5", [paiement(27000, "2026-10-01", "Refused")])
    inscrit("6", [paiement(27000, "2026-10-01", "Authorized", "MoneyIn")], state="Canceled")
    db_session.commit()

    faits = money.to_come(db_session, ecole.id, 1, "2026-11-01")
    assert faits["echeancesAVenir"] == [
        {"date": "2026-12-05", "echeance": 2, "montant": 180.0, "adherents": 2},
        {"date": "2027-02-05", "echeance": 3, "montant": 180.0, "adherents": 2},
    ]
    assert faits["encaisseNonVerse"] == 540.0 and faits["totalSur"] == 900.0
    assert (faits["adherentsEnUneFois"], faits["adherentsEnPlusieursFois"]) == (3, 2)
    assert faits["nonComptes"] == {"impayes": 270.0, "resilies": 1}
    assert faits["campagne"] == "Adhésions 2026-2027" and faits["relueLe"] == "2026-11-18"
    assert faits["aResynchroniser"] is False

    core = type("Core", (), {"helloasso_money": staticmethod(money.to_come)})()
    lire = argent_helloasso(core)
    assert lire(db_session, ecole.id, 1, "2026-11-01")["totalSur"] == 900.0
    set_enabled(db_session, ecole.id, MODULES, "helloasso", False)
    assert lire(db_session, ecole.id, 1, "2026-11-01") is None


# --- Étape 10 : statistiques de la saison (spec §7.8) ---


def test_projection_des_salaires():
    """Montant des 3 derniers mois s'ils sont identiques, sinon moyenne des
    6 derniers mois complets ; mois restants jusqu'à la fin de la saison."""
    from datetime import date

    from helloasso.stats import payroll

    def op(jour, montant, categorie):
        return {"date": jour, "amount": montant, "category": categorie}

    reguliers = [op(f"2026-{m:02d}-28", -1000, "Salaires") for m in (9, 10, 11)] + [
        op(f"2026-{m:02d}-15", -240, "URSSAF") for m in (9, 10, 11)
    ]
    # Novembre payé : de décembre à août, 9 mois.
    assert payroll(reguliers, date(2027, 8, 31), date(2026, 11, 30)) == {
        "total": 11160.0, "monthly": 1240.0, "months": 9, "regular": True,
    }
    # Mois sauté puis doublé : moyenne de septembre (1er paiement) à novembre.
    irreguliers = [op("2026-09-28", -1000, "Salaires"), op("2026-11-28", -2000, "Salaires")]
    projection = payroll(irreguliers, date(2027, 8, 31), date(2026, 12, 5))
    assert (projection["monthly"], projection["months"], projection["regular"]) == (1000.0, 9, False)


def test_statistiques_de_la_saison(client, db_session, ecole, campagnes, monkeypatch):
    """Majeurs, mineurs, prix moyen ; encaissements (la banque dit ce qui est
    arrivé) ; soldes et projection seulement avec l'Accès au Financier."""
    from app import main
    from comptes import roles

    def paiement(montant, etat, jour, sortie=None, versement=None):
        return {"amount": montant, "date": f"{jour}T10:00:00", "state": etat, "means": "Card", "installment": 1,
                "cash_out_state": sortie, "cash_out_date": versement and f"{versement}T08:00:00"}

    naissance = lambda d: [{"id": "1", "name": "Date de naissance", "type": "Date", "answer": d}]  # noqa: E731
    lea = {**_inscrit("1", "Léa", "Martin", "p@test.fr", naissance("14/03/1990"), montant=24000), "payments": [
        paiement(8000, "Authorized", "2026-09-02", "CashedOut", "2026-10-07"),
        paiement(8000, "Authorized", "2026-10-02", "Transfered"),
        paiement(8000, "Pending", "2026-12-02"),
    ]}
    noe = {**_inscrit("2", "Noé", "Lefèvre", "n@test.fr", naissance("11/10/2012"), montant=12000), "payments": [
        paiement(12000, "Authorized", "2026-11-02", "WaitingForCashOutConfirmation", "2026-11-07"),
    ]}
    partie = _inscrit("3", "Tom", "Benali", "t@test.fr", state="Canceled")
    _saison_imposee(client, ecole, monkeypatch, [lea, noe, partie])

    comptes = {
        "accounts": [{"name": "Compte courant", "balance": 4820.0, "asOf": "2026-11-15"},
                     {"name": "Livret", "balance": 6000.0, "asOf": "2026-11-15"}],
        "rows": [
            # Le versement du 07/10 est arrivé le 10/10 ; celui du 07/11 pas encore.
            {"date": "2026-10-10", "label": "VIR HELLOASSOPAY HELLOASSO 3711911 07-10-2026", "amount": 80.0,
             "category": "Cotisations en ligne"},
            *[{"date": f"2026-{m:02d}-28", "label": "VIR SALAIRE", "amount": -1240.0, "category": "Salaires"}
              for m in (8, 9, 10)],
        ],
    }
    monkeypatch.setattr(main.core.helloasso_stats, "ledger", lambda db, org_id: comptes)
    monkeypatch.setattr(main.core.helloasso_stats, "licences", lambda db, org_id, n: {"count": n + 1, "price": 24})
    url = f"/ecoles/{ecole.id}/helloasso/statistiques"
    stats = client.get(url).json()
    assert (stats["members"], stats["adults"], stats["minors"], stats["average_price"], stats["total_price"]) == (
        2, 1, 1, 180.0, 360.0,
    )
    caisse = stats["cash"]
    assert caisse["on_account"] == [{"date": "2026-10-10", "requested": "2026-10-07", "amount": 80.0, "payments": 1}]
    assert (caisse["in_transit"], caisse["held"], caisse["to_receive"]) == (120.0, 80.0, 280.0)
    assert caisse["upcoming"] == [{"month": "2026-12", "amount": 80.0, "payments": 1}]
    assert stats["balance"] == 10820.0 and [a["name"] for a in stats["accounts"]] == ["Compte courant", "Livret"]
    assert stats["licences"] == {"count": 3, "price": 24}
    salaires = stats["payroll"]["total"]
    assert stats["projected"] == round(10820.0 + 280.0 - salaires - 72, 2)

    monkeypatch.setattr(roles, "has_right", lambda compte, droit: False)
    stats = client.get(url).json()
    assert stats["finances"] is False and stats["cash"]["to_receive"] == 280.0
    assert (stats["accounts"], stats["balance"], stats["payroll"], stats["projected"]) == (None, None, None, None)


def test_statistiques_branchees_sur_le_financier_et_la_ffst(db_session, ecole):
    """Contretemps relie les statistiques au Financier et à la FFST ; une
    école sans le Financier ou sans la FFST n'a ni solde ni licences."""
    from app import main
    from app.modules import MODULES
    from registry.activation import set_enabled

    sources = main.core.helloasso_stats
    assert sources.ledger(db_session, ecole.id)["accounts"] == []
    assert sources.licences(db_session, ecole.id, 10) is None  # FFST éteinte
    set_enabled(db_session, ecole.id, MODULES, "finances", False)
    assert sources.ledger(db_session, ecole.id) is None


def test_ordre_des_adherents_comme_sambo_admin(client, db_session, ecole, campagnes, monkeypatch):
    """Seb 18/11 : le tableau suit l'ordre de Sambo Admin, celui de HelloAsso :
    la commande la plus récente d'abord, puis les adhérents d'une même
    commande dans leur ordre."""
    from comptes import Compte

    def inscrit(item_id, prenom, nom, commande, jour):
        return {**_inscrit(item_id, prenom, nom, f"{prenom}@test.fr"), "order_id": commande,
                "order_date": f"2026-{jour}T10:00:00"}

    _saison_imposee(client, ecole, monkeypatch, [
        inscrit("10", "Ana", "Zola", "c1", "09-02"),
        inscrit("30", "Léo", "Abel", "c3", "10-15"),
        inscrit("21", "Noé", "Moreau", "c2", "09-20"),
        inscrit("22", "Lou", "Moreau", "c2", "09-20"),
    ])
    lignes = client.get(f"/ecoles/{ecole.id}/helloasso/adherents").json()["members"]
    par_rang = sorted(lignes.items(), key=lambda kv: kv[1]["rank"])
    assert [db_session.get(Compte, int(i)).prenom for i, _ in par_rang] == ["Léo", "Noé", "Lou", "Ana"]


def test_echeances_a_venir(client, db_session, ecole, campagnes, monkeypatch):
    """Impayés HelloAsso montre aussi les échéances à venir (Seb 18/11) :
    nom, somme, date, par date ; ni les payées, ni les refusées, ni celles
    d'une adhésion résiliée."""
    def echeance(montant, etat, date):
        return {"amount": montant, "date": f"{date}T10:00:00", "state": etat, "means": "Card", "installment": 1}

    tom = {**_inscrit("1", "Tom", "Benali", "t@test.fr", montant=24000), "payments": [
        echeance(8000, "Authorized", "2026-09-02"),
        echeance(8000, "Refused", "2026-10-02"),
        echeance(8000, "Pending", "2027-01-02"),
    ]}
    ines = {**_inscrit("2", "Inès", "Navarro", "i@test.fr", montant=16000), "payments": [
        echeance(8000, "Authorized", "2026-09-05"),
        echeance(8000, "Pending", "2026-12-05"),
    ]}
    partie = {**_inscrit("3", "Enzo", "Roux", "e@test.fr", state="Canceled"), "payments": [
        echeance(6000, "Pending", "2026-12-01"),
    ]}
    _saison_imposee(client, ecole, monkeypatch, [tom, ines, partie])
    lu = client.get(f"/ecoles/{ecole.id}/helloasso/impayes").json()
    assert [(e["last_name"], e["first_name"], e["amount"], e["date"][:10]) for e in lu["upcoming"]] == [
        ("Navarro", "Inès", 8000, "2026-12-05"),
        ("Benali", "Tom", 8000, "2027-01-02"),
    ]
    assert lu["upcoming"][0]["member_id"] is not None
