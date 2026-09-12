"""Tests bout-en-bout du paiement HelloAsso (voir
spec/SPEC-inscription.md et inscriptions/helloasso.py) — `requests` est
systématiquement remplacé par un faux, comme dans
test_inscriptions_helloasso.py : aucun compte sandbox réel n'est
configuré en test, un vrai appel échouerait de toute façon.

Le client HelloAsso appelé ici est le VRAI singleton de l'app (voir
app.main:inscriptions_client.helloasso, même patron que
test_notifications.py pour le singleton Notifications) — ses attributs
sont modifiés via monkeypatch pour le rendre "actif" le temps du test,
jamais un nouveau `Inscriptions(...)` construit à part."""

import shutil

import pytest
from app.main import inscriptions_client
from cours import CoursService
from ecoles import Ecoles
from inscriptions import helloasso as helloasso_module
from inscriptions.stockage import DOSSIER_INSCRIPTIONS

NOMS_COURS_REELS = ["Éveil", "Class Inter"]


def _creer_ecole_avec_cours(db_session):
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    cours_service = CoursService()
    cours = {}
    for nom in NOMS_COURS_REELS:
        cours[nom] = cours_service.create(db_session, ecole_id=ecole.id, nom=nom)
    return ecole, cours


@pytest.fixture()
def _nettoyage_dossier():
    dossiers = []
    yield dossiers
    for dossier in dossiers:
        shutil.rmtree(dossier, ignore_errors=True)


def _donnees_formulaire(cours_ids, **overrides):
    donnees = {
        "eleve_nom": "Dupont",
        "eleve_prenom": "Marie",
        "eleve_date_naissance": "2018-11-17",
        "eleve_email": "marie@example.com",
        "cours_ids": cours_ids,
        "reglement_lu_approuve": True,
        "signataire_nom": "Jean Dupont",
        "moyen_paiement": "helloasso",
        "paiement_nb_echeances": 1,
    }
    donnees.update(overrides)
    return donnees


class _FausseReponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self.text = str(json_data)

    def json(self):
        return self._json


@pytest.fixture()
def _helloasso_actif(monkeypatch):
    """Rend le singleton HelloAsso "actif" et lui fait toujours renvoyer
    un faux token — voir docstring du module."""
    ha = inscriptions_client.helloasso
    monkeypatch.setattr(ha, "client_id", "id-test")
    monkeypatch.setattr(ha, "client_secret", "secret-test")
    monkeypatch.setattr(ha, "organization_slug", "asso-test")
    monkeypatch.setattr(ha, "actif", True)
    monkeypatch.setattr(ha, "_access_token", None)
    monkeypatch.setattr(ha, "_expire_a", 0.0)
    monkeypatch.setattr(
        helloasso_module.requests,
        "post",
        lambda *a, **k: _FausseReponse({"access_token": "tok", "expires_in": 1799}),
    )
    return ha


def test_paiement_helloasso_refuse_si_moyen_paiement_different(
    client, db_session, _nettoyage_dossier, _helloasso_actif
):
    ecole, cours = _creer_ecole_avec_cours(db_session)
    _nettoyage_dossier.append(DOSSIER_INSCRIPTIONS / str(ecole.id))
    corps = client.post(
        "/inscriptions",
        params={"ecole_id": ecole.id},
        json=_donnees_formulaire([cours["Éveil"].id], moyen_paiement="cheque"),
    ).json()

    reponse = client.post(
        f"/inscriptions/{corps['token_public']}/paiement/helloasso",
        json={"retour_url": "https://exemple.fr/retour"},
    )
    assert reponse.status_code == 400


def test_paiement_helloasso_donnee_rejetee_renvoie_400_avec_message(
    client, db_session, _nettoyage_dossier, _helloasso_actif, monkeypatch
):
    """Voir helloasso.py:HelloAssoError — un 400 avec de vrais messages
    HelloAsso (ex. nom du payeur invalide, constaté en sandbox) doit
    remonter en 400 avec ce message, pas en 503 générique (réservé à une
    vraie panne)."""
    ecole, cours = _creer_ecole_avec_cours(db_session)
    _nettoyage_dossier.append(DOSSIER_INSCRIPTIONS / str(ecole.id))
    corps = client.post(
        "/inscriptions",
        params={"ecole_id": ecole.id},
        json=_donnees_formulaire([cours["Éveil"].id]),
    ).json()

    monkeypatch.setattr(
        helloasso_module.requests,
        "request",
        lambda *a, **k: _FausseReponse(
            {"errors": [{"code": "ArgumentInvalid", "message": "Votre nom doit comporter au moins une voyelle"}]},
            status_code=400,
        ),
    )
    reponse = client.post(
        f"/inscriptions/{corps['token_public']}/paiement/helloasso",
        json={"retour_url": "https://exemple.fr/retour"},
    )
    assert reponse.status_code == 400
    assert "voyelle" in reponse.json()["detail"]


def test_paiement_helloasso_indisponible_si_non_configure(
    client, db_session, _nettoyage_dossier, monkeypatch
):
    # Pas de fixture _helloasso_actif ici -> force le singleton
    # "inactif" explicitement : un .env local de dev peut légitimement
    # avoir de vraies clés sandbox configurées (voir
    # spec/SPEC-inscription.md §4), ce test doit rester vrai peu importe.
    monkeypatch.setattr(inscriptions_client.helloasso, "actif", False)
    ecole, cours = _creer_ecole_avec_cours(db_session)
    _nettoyage_dossier.append(DOSSIER_INSCRIPTIONS / str(ecole.id))
    corps = client.post(
        "/inscriptions",
        params={"ecole_id": ecole.id},
        json=_donnees_formulaire([cours["Éveil"].id]),
    ).json()

    reponse = client.post(
        f"/inscriptions/{corps['token_public']}/paiement/helloasso",
        json={"retour_url": "https://exemple.fr/retour"},
    )
    assert reponse.status_code == 503


def test_paiement_helloasso_initie_1x(
    client, db_session, _nettoyage_dossier, _helloasso_actif, monkeypatch
):
    ecole, cours = _creer_ecole_avec_cours(db_session)
    _nettoyage_dossier.append(DOSSIER_INSCRIPTIONS / str(ecole.id))
    corps = client.post(
        "/inscriptions",
        params={"ecole_id": ecole.id},
        json=_donnees_formulaire([cours["Éveil"].id], paiement_nb_echeances=1),
    ).json()

    appels = {}

    def _fake_request(methode, url, headers=None, timeout=None, **kwargs):
        appels["json"] = kwargs.get("json")
        return _FausseReponse({"id": 777, "redirectUrl": "https://helloasso-sandbox.com/pay/777"})

    monkeypatch.setattr(helloasso_module.requests, "request", _fake_request)

    reponse = client.post(
        f"/inscriptions/{corps['token_public']}/paiement/helloasso",
        json={"retour_url": "https://exemple.fr/retour"},
    )
    assert reponse.status_code == 200
    assert reponse.json() == {"redirect_url": "https://helloasso-sandbox.com/pay/777"}
    assert "terms" not in appels["json"]
    # Adhésion + 3 trimestres d'Éveil (110€/trim) en 1 seule échéance.
    assert appels["json"]["totalAmount"] == round((40.0 + 110.0 * 3) * 100)


def test_paiement_helloasso_initie_3x_avec_terms(
    client, db_session, _nettoyage_dossier, _helloasso_actif, monkeypatch
):
    ecole, cours = _creer_ecole_avec_cours(db_session)
    _nettoyage_dossier.append(DOSSIER_INSCRIPTIONS / str(ecole.id))
    corps = client.post(
        "/inscriptions",
        params={"ecole_id": ecole.id},
        json=_donnees_formulaire([cours["Éveil"].id], paiement_nb_echeances=3),
    ).json()

    appels = {}

    def _fake_request(methode, url, headers=None, timeout=None, **kwargs):
        appels["json"] = kwargs.get("json")
        return _FausseReponse({"id": 778, "redirectUrl": "https://helloasso-sandbox.com/pay/778"})

    monkeypatch.setattr(helloasso_module.requests, "request", _fake_request)

    reponse = client.post(
        f"/inscriptions/{corps['token_public']}/paiement/helloasso",
        json={"retour_url": "https://exemple.fr/retour"},
    )
    assert reponse.status_code == 200
    # Inscription en septembre : les 3 trimestres (oct/jan/avril) sont
    # encore dans le futur -> seule l'adhésion est payée immédiatement,
    # les 3 trimestres deviennent des `terms` (voir tarifs.py:dates_trimestres).
    assert len(appels["json"]["terms"]) == 3
    assert appels["json"]["initialAmount"] == round(40.0 * 100)


def test_verifier_paiement_helloasso_marque_paye(
    client, db_session, _nettoyage_dossier, _helloasso_actif, monkeypatch
):
    ecole, cours = _creer_ecole_avec_cours(db_session)
    _nettoyage_dossier.append(DOSSIER_INSCRIPTIONS / str(ecole.id))
    corps = client.post(
        "/inscriptions",
        params={"ecole_id": ecole.id},
        json=_donnees_formulaire([cours["Éveil"].id]),
    ).json()
    token = corps["token_public"]

    # Pas encore payé -> pas encore finalisé (voir
    # inscriptions.py:_finaliser, déclenché seulement à la confirmation).
    assert client.get(f"/inscriptions/{token}/dossier.pdf").status_code == 404

    monkeypatch.setattr(
        helloasso_module.requests,
        "request",
        lambda *a, **k: _FausseReponse({"id": 999, "redirectUrl": "https://x/pay"}),
    )
    client.post(
        f"/inscriptions/{token}/paiement/helloasso", json={"retour_url": "https://exemple.fr"}
    )

    appels_email = []
    monkeypatch.setattr(
        inscriptions_client.email, "envoyer_confirmation", lambda *a, **k: appels_email.append(1)
    )
    monkeypatch.setattr(
        helloasso_module.requests,
        "request",
        lambda *a, **k: _FausseReponse(
            {"order": {"payments": [{"state": "Authorized"}]}}
        ),
    )
    reponse = client.post(f"/inscriptions/{token}/paiement/helloasso/verifier")
    assert reponse.status_code == 200
    assert reponse.json()["statut_paiement"] == "paye"
    # Payé -> finalisé (PDF généré, email tenté).
    assert client.get(f"/inscriptions/{token}/dossier.pdf").status_code == 200
    assert len(appels_email) == 1

    # Une 2e vérification (ex. webhook après le retour navigateur, voir
    # spec/SPEC-inscription.md) ne doit PAS finaliser une 2e fois.
    reponse2 = client.post(f"/inscriptions/{token}/paiement/helloasso/verifier")
    assert reponse2.status_code == 200
    assert len(appels_email) == 1


def test_choisir_paiement_cheque_finalise_immediatement(
    client, db_session, _nettoyage_dossier
):
    ecole, cours = _creer_ecole_avec_cours(db_session)
    _nettoyage_dossier.append(DOSSIER_INSCRIPTIONS / str(ecole.id))
    corps = client.post(
        "/inscriptions",
        params={"ecole_id": ecole.id},
        json={
            "eleve_nom": "Dupont",
            "eleve_prenom": "Marie",
            "eleve_date_naissance": "2018-11-17",
            "eleve_email": "marie@example.com",
            "cours_ids": [cours["Éveil"].id],
            "reglement_lu_approuve": True,
            "signataire_nom": "Jean Dupont",
        },
    ).json()
    token = corps["token_public"]
    assert client.get(f"/inscriptions/{token}/dossier.pdf").status_code == 404

    reponse = client.post(
        f"/inscriptions/{token}/paiement/choix",
        json={"moyen_paiement": "cheque", "paiement_nb_echeances": 3},
    )
    assert reponse.status_code == 200
    corps_choix = reponse.json()
    assert corps_choix["moyen_paiement"] == "cheque"
    assert corps_choix["paiement_nb_echeances"] == 3
    assert client.get(f"/inscriptions/{token}/dossier.pdf").status_code == 200


def test_choisir_paiement_moyen_invalide_400(client, db_session, _nettoyage_dossier):
    ecole, cours = _creer_ecole_avec_cours(db_session)
    _nettoyage_dossier.append(DOSSIER_INSCRIPTIONS / str(ecole.id))
    corps = client.post(
        "/inscriptions",
        params={"ecole_id": ecole.id},
        json={
            "eleve_nom": "Dupont",
            "eleve_prenom": "Marie",
            "eleve_date_naissance": "2018-11-17",
            "eleve_email": "marie@example.com",
            "cours_ids": [cours["Éveil"].id],
            "reglement_lu_approuve": True,
            "signataire_nom": "Jean Dupont",
        },
    ).json()
    reponse = client.post(
        f"/inscriptions/{corps['token_public']}/paiement/choix",
        json={"moyen_paiement": "virement", "paiement_nb_echeances": 1},
    )
    assert reponse.status_code == 400


def test_choisir_paiement_token_inconnu_404(client, db_session):
    reponse = client.post(
        "/inscriptions/token-inexistant/paiement/choix",
        json={"moyen_paiement": "cheque", "paiement_nb_echeances": 1},
    )
    assert reponse.status_code == 404


def test_webhook_helloasso_declenche_la_verification(
    client, db_session, _nettoyage_dossier, _helloasso_actif, monkeypatch
):
    ecole, cours = _creer_ecole_avec_cours(db_session)
    _nettoyage_dossier.append(DOSSIER_INSCRIPTIONS / str(ecole.id))
    corps = client.post(
        "/inscriptions",
        params={"ecole_id": ecole.id},
        json=_donnees_formulaire([cours["Éveil"].id]),
    ).json()
    token = corps["token_public"]

    monkeypatch.setattr(
        helloasso_module.requests,
        "request",
        lambda *a, **k: _FausseReponse({"id": 555, "redirectUrl": "https://x/pay"}),
    )
    client.post(
        f"/inscriptions/{token}/paiement/helloasso", json={"retour_url": "https://exemple.fr"}
    )

    monkeypatch.setattr(
        helloasso_module.requests,
        "request",
        lambda *a, **k: _FausseReponse({"order": {"payments": [{"state": "Authorized"}]}}),
    )
    reponse = client.post(
        "/inscriptions/paiement/helloasso/notification",
        json={"eventType": "Payment", "data": {"order": {"checkoutIntentId": 555}}},
    )
    assert reponse.status_code == 204

    verification = client.get(f"/inscriptions/{token}")
    assert verification.json()["statut_paiement"] == "paye"


def test_webhook_helloasso_corps_inconnu_ne_plante_pas(client, db_session):
    reponse = client.post("/inscriptions/paiement/helloasso/notification", json={"foo": "bar"})
    assert reponse.status_code == 204
