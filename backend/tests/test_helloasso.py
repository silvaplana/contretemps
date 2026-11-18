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
        {"id": "11", "name": "Genre", "type": "", "answer": "F"},
    ]
    assert inscrits[0]["payer_name"] == "Paul" and inscrits[1]["payer_name"] == "Ana Noir"
    assert inscrits[0]["payments"] == [
        {"amount": 9000, "date": "2026-09-02", "state": "Authorized", "means": "Card", "installment": 1},
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
        "imposed": False, "form_name": None, "can_refresh": False, "members": {},
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
    assert lignes["Léa"] == {"amount": 16000, "discount_code": "FRATRIE", "state": "Processed",
                             "cancelled": False, "photo": True}
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
