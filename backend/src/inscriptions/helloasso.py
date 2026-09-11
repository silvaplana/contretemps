"""Paiement en ligne via HelloAsso (Checkout Intent API, voir
spec/SPEC-inscription.md et dev.helloasso.com) — sandbox d'abord (compte
de test créé sur https://auth.helloasso-sandbox.com/inscription,
indépendant de la vraie association), même philosophie de désactivation
silencieuse que notifications/email_envoi.py : sans identifiants
configurés, `actif` == False, aucun appel HTTP n'est jamais tenté.

⚠️ Vérification de paiement : ne JAMAIS faire confiance à un simple
retour navigateur (returnUrl) ni au corps d'une notification webhook non
signée — la vérification de signature HMAC est réservée aux comptes
HelloAsso "partenaire" (voir dev.helloasso.com/docs/secure-webhook), pas
notre cas. Toujours ré-interroger `recuperer_checkout_intent` (GET,
source de vérité côté HelloAsso) avant de marquer un paiement confirmé.
"""

from __future__ import annotations

import logging
import os
import re
import time

import requests

from .tarifs import Echeance

logger = logging.getLogger(__name__)

# Sandbox par défaut (voir .env.example) — bascule vers
# https://api.helloasso.com en production une fois un vrai compte
# HelloAsso créé pour l'école (voir spec/SPEC-inscription.md §3).
BASE_URL_DEFAUT = "https://api.helloasso-sandbox.com"


def nettoyer_nom_payeur(texte: str) -> str:
    """HelloAsso refuse tout chiffre dans firstName/lastName (constaté en
    sandbox : "Votre nom ne doit pas contenir de chiffres") — retire les
    chiffres, garde le reste tel quel (accents/espaces/tirets acceptés).
    Un vrai nom de famille n'en contient jamais, mais une faute de frappe
    ou un pseudo ne doit jamais faire échouer tout le paiement."""
    return re.sub(r"\d+", "", texte).strip() or "-"


class HelloAssoError(Exception):
    """Levée sur tout échec d'appel à l'API HelloAsso (réseau, 4xx/5xx) —
    jamais avalée silencieusement ici : contrairement à l'email/Excel,
    l'appelant (inscriptions.py) doit savoir que le paiement n'a pas pu
    être initié pour prévenir la famille, pas juste continuer comme si
    de rien n'était.

    `status_code`/`messages_api` : voir receiver.py — un 400 avec de
    vrais messages (ex. "Votre nom doit comporter au moins une voyelle",
    constaté en sandbox) est une DONNÉE rejetée, pas une panne : mérite
    un message clair à la famille, pas le 503 générique réservé à une
    vraie indisponibilité (réseau, authentification, 5xx)."""

    def __init__(self, message: str, status_code: int | None = None, messages_api: list[str] | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.messages_api = messages_api or []


class HelloAsso:
    def __init__(self) -> None:
        self.base_url = os.environ.get("HELLOASSO_API_BASE", BASE_URL_DEFAUT)
        self.client_id = os.environ.get("HELLOASSO_CLIENT_ID")
        self.client_secret = os.environ.get("HELLOASSO_CLIENT_SECRET")
        self.organization_slug = os.environ.get("HELLOASSO_ORGANIZATION_SLUG")
        self.actif = bool(self.client_id and self.client_secret and self.organization_slug)
        self._access_token: str | None = None
        self._expire_a: float = 0.0

    def _obtenir_token(self) -> str:
        """Voir dev.helloasso.com/docs/getting-started — un access_token
        dure 30 min ; on le garde en mémoire process (pas en base : un
        redémarrage du backend en redemande juste un nouveau, coût
        négligeable) plutôt que d'en redemander un à chaque appel."""
        if not self.actif:
            raise HelloAssoError("HelloAsso non configuré (identifiants manquants)")
        if self._access_token and time.monotonic() < self._expire_a:
            return self._access_token
        reponse = requests.post(
            f"{self.base_url}/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=10,
        )
        if not reponse.ok:
            raise HelloAssoError(f"Authentification HelloAsso échouée ({reponse.status_code})")
        corps = reponse.json()
        self._access_token = corps["access_token"]
        # Marge de 60s avant l'expiration réelle, pour ne jamais utiliser
        # un token périmé pile au moment de l'appel suivant.
        self._expire_a = time.monotonic() + corps["expires_in"] - 60
        return self._access_token

    def _appel(self, methode: str, chemin: str, **kwargs) -> dict:
        token = self._obtenir_token()
        reponse = requests.request(
            methode,
            f"{self.base_url}/v5/organizations/{self.organization_slug}{chemin}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
            **kwargs,
        )
        if not reponse.ok:
            messages_api = []
            try:
                messages_api = [e.get("message", "") for e in reponse.json().get("errors", [])]
            except Exception:
                pass
            raise HelloAssoError(
                f"Appel HelloAsso {methode} {chemin} échoué ({reponse.status_code}) : "
                f"{reponse.text[:300]}",
                status_code=reponse.status_code,
                messages_api=messages_api,
            )
        return reponse.json()

    def creer_checkout_intent(
        self,
        echeances: list[Echeance],
        nom_item: str,
        back_url: str,
        error_url: str,
        return_url: str,
        payer: dict | None = None,
        metadata: dict | None = None,
    ) -> dict:
        """Crée l'intention de paiement — `echeances` : voir
        tarifs.py:calculer_echeances_helloasso (1 ou 3 échéances, la 1ʳᵉ
        toujours payée immédiatement). Renvoie {"id":..., "redirect_url":
        ...} — rediriger le navigateur vers `redirect_url` pour que la
        famille paie."""
        initial, *termes = echeances
        corps = {
            "totalAmount": round(sum(e.montant for e in echeances) * 100),
            "initialAmount": round(initial.montant * 100),
            "itemName": nom_item,
            "backUrl": back_url,
            "errorUrl": error_url,
            "returnUrl": return_url,
            "containsDonation": False,
        }
        if termes:
            corps["terms"] = [
                {"amount": round(t.montant * 100), "date": t.date_prelevement.isoformat()}
                for t in termes
            ]
        if payer:
            corps["payer"] = payer
        if metadata:
            corps["metadata"] = metadata
        resultat = self._appel("POST", "/checkout-intents", json=corps)
        return {"id": resultat["id"], "redirect_url": resultat["redirectUrl"]}

    def recuperer_checkout_intent(self, checkout_intent_id: int) -> dict:
        """Source de vérité sur l'état d'un paiement — voir docstring du
        module. Renvoie le JSON brut de l'API (voir dev.helloasso.com/
        reference : order.payments[].state, "Authorized" = payé par
        carte ; SEPA/chèque restent "Pending"/"Registered" un temps)."""
        return self._appel("GET", f"/checkout-intents/{checkout_intent_id}")
