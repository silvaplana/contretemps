"""Tests de helloasso.py — `requests` systématiquement remplacé par un
faux (même patron que test_notifications.py:webpush) : un vrai appel
échouerait de toute façon (aucun compte sandbox configuré en test)."""

import datetime as dt

import pytest
from inscriptions import helloasso as helloasso_module
from inscriptions.helloasso import HelloAsso, HelloAssoError, nettoyer_nom_payeur
from inscriptions.tarifs import Echeance


class _FausseReponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self.text = str(json_data)

    def json(self):
        return self._json


def _client_configure(monkeypatch) -> HelloAsso:
    monkeypatch.setenv("HELLOASSO_CLIENT_ID", "id-test")
    monkeypatch.setenv("HELLOASSO_CLIENT_SECRET", "secret-test")
    monkeypatch.setenv("HELLOASSO_ORGANIZATION_SLUG", "asso-test")
    return HelloAsso()


def test_non_configure_actif_false(monkeypatch):
    # `delenv` explicite (pas juste "absent par défaut") : un .env local
    # de dev peut légitimement contenir de vraies clés sandbox (voir
    # spec/SPEC-inscription.md §4) — piège trouvé en configurant les
    # miennes en local, ce test devenait "actif" sans le vouloir.
    monkeypatch.delenv("HELLOASSO_CLIENT_ID", raising=False)
    monkeypatch.delenv("HELLOASSO_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("HELLOASSO_ORGANIZATION_SLUG", raising=False)
    client = HelloAsso()
    assert client.actif is False
    with pytest.raises(HelloAssoError):
        client._obtenir_token()


def test_obtenir_token_appelle_le_bon_endpoint(monkeypatch):
    client = _client_configure(monkeypatch)
    appels = {}

    def _fake_post(url, data=None, timeout=None):
        appels["url"] = url
        appels["data"] = data
        return _FausseReponse({"access_token": "abc123", "expires_in": 1799})

    monkeypatch.setattr(helloasso_module.requests, "post", _fake_post)

    token = client._obtenir_token()
    assert token == "abc123"
    assert appels["url"] == "https://api.helloasso-sandbox.com/oauth2/token"
    assert appels["data"] == {
        "grant_type": "client_credentials",
        "client_id": "id-test",
        "client_secret": "secret-test",
    }


def test_obtenir_token_mis_en_cache(monkeypatch):
    """2 appels rapprochés -> un seul POST /oauth2/token."""
    client = _client_configure(monkeypatch)
    nb_appels = {"post": 0}

    def _fake_post(url, data=None, timeout=None):
        nb_appels["post"] += 1
        return _FausseReponse({"access_token": "abc123", "expires_in": 1799})

    monkeypatch.setattr(helloasso_module.requests, "post", _fake_post)

    assert client._obtenir_token() == "abc123"
    assert client._obtenir_token() == "abc123"
    assert nb_appels["post"] == 1


def test_obtenir_token_echec_leve_helloassoerror(monkeypatch):
    client = _client_configure(monkeypatch)
    monkeypatch.setattr(
        helloasso_module.requests, "post", lambda *a, **k: _FausseReponse({}, status_code=401)
    )
    with pytest.raises(HelloAssoError):
        client._obtenir_token()


def test_creer_checkout_intent_1x_sans_terms(monkeypatch):
    client = _client_configure(monkeypatch)
    monkeypatch.setattr(
        helloasso_module.requests,
        "post",
        lambda *a, **k: _FausseReponse({"access_token": "tok", "expires_in": 1799}),
    )
    appels = {}

    def _fake_request(methode, url, headers=None, timeout=None, **kwargs):
        appels["methode"] = methode
        appels["url"] = url
        appels["headers"] = headers
        appels["json"] = kwargs.get("json")
        return _FausseReponse({"id": 42, "redirectUrl": "https://helloasso-sandbox.com/pay/42"})

    monkeypatch.setattr(helloasso_module.requests, "request", _fake_request)

    echeances = [Echeance(montant=370.0, date_prelevement=None)]
    resultat = client.creer_checkout_intent(
        echeances,
        nom_item="Inscription Julie Dupont",
        back_url="https://x/back",
        error_url="https://x/error",
        return_url="https://x/return",
    )

    assert resultat == {"id": 42, "redirect_url": "https://helloasso-sandbox.com/pay/42"}
    assert appels["methode"] == "POST"
    assert appels["url"] == "https://api.helloasso-sandbox.com/v5/organizations/asso-test/checkout-intents"
    assert appels["headers"] == {"Authorization": "Bearer tok"}
    corps = appels["json"]
    assert corps["totalAmount"] == 37000
    assert corps["initialAmount"] == 37000
    assert "terms" not in corps


def test_creer_checkout_intent_3x_avec_terms(monkeypatch):
    client = _client_configure(monkeypatch)
    monkeypatch.setattr(
        helloasso_module.requests,
        "post",
        lambda *a, **k: _FausseReponse({"access_token": "tok", "expires_in": 1799}),
    )
    appels = {}

    def _fake_request(methode, url, headers=None, timeout=None, **kwargs):
        appels["json"] = kwargs.get("json")
        return _FausseReponse({"id": 1, "redirectUrl": "https://x/pay"})

    monkeypatch.setattr(helloasso_module.requests, "request", _fake_request)

    echeances = [
        Echeance(montant=150.0, date_prelevement=None),
        Echeance(montant=110.0, date_prelevement=dt.date(2026, 10, 11)),
        Echeance(montant=110.0, date_prelevement=dt.date(2026, 11, 11)),
    ]
    client.creer_checkout_intent(
        echeances,
        nom_item="Inscription Julie Dupont",
        back_url="https://x/back",
        error_url="https://x/error",
        return_url="https://x/return",
    )

    corps = appels["json"]
    assert corps["totalAmount"] == 37000
    assert corps["initialAmount"] == 15000
    assert corps["terms"] == [
        {"amount": 11000, "date": "2026-10-11"},
        {"amount": 11000, "date": "2026-11-11"},
    ]


def test_recuperer_checkout_intent(monkeypatch):
    client = _client_configure(monkeypatch)
    monkeypatch.setattr(
        helloasso_module.requests,
        "post",
        lambda *a, **k: _FausseReponse({"access_token": "tok", "expires_in": 1799}),
    )
    appels = {}

    def _fake_request(methode, url, headers=None, timeout=None, **kwargs):
        appels["methode"] = methode
        appels["url"] = url
        return _FausseReponse({"id": 42, "order": {"payments": [{"state": "Authorized"}]}})

    monkeypatch.setattr(helloasso_module.requests, "request", _fake_request)

    resultat = client.recuperer_checkout_intent(42)
    assert appels["methode"] == "GET"
    assert appels["url"] == (
        "https://api.helloasso-sandbox.com/v5/organizations/asso-test/checkout-intents/42"
    )
    assert resultat["order"]["payments"][0]["state"] == "Authorized"


def test_appel_echec_leve_helloassoerror(monkeypatch):
    client = _client_configure(monkeypatch)
    monkeypatch.setattr(
        helloasso_module.requests,
        "post",
        lambda *a, **k: _FausseReponse({"access_token": "tok", "expires_in": 1799}),
    )
    monkeypatch.setattr(
        helloasso_module.requests,
        "request",
        lambda *a, **k: _FausseReponse({"error": "not found"}, status_code=404),
    )
    with pytest.raises(HelloAssoError):
        client.recuperer_checkout_intent(999)


def test_nettoyer_nom_payeur_retire_les_chiffres():
    """Voir spec/SPEC-inscription.md §4 : HelloAsso refuse tout chiffre
    dans firstName/lastName ("Votre nom ne doit pas contenir de
    chiffres", constaté en sandbox)."""
    assert nettoyer_nom_payeur("TestHA2") == "TestHA"
    assert nettoyer_nom_payeur("Marie-Zoé") == "Marie-Zoé"
    assert nettoyer_nom_payeur("  42  ") == "-"
