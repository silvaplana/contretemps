"""Client HTTP minimal pour l'API Enable Banking (https://enablebanking.com),
agrégateur bancaire PSD2 : lit soldes et opérations des comptes de
l'organisation après autorisation chez sa banque. Repris de Sambo Admin
(`test-python`, backend/src/bankaccounts/enablebanking.py) ; changements :
la banque est donnée à chaque autorisation (une par organisation) et la
liste des banques se lit (`list_banks`).

Authentification de l'application : un JWT signé RS256 avec la clé privée
(.pem, téléchargée à la création de l'application dans le Control Panel),
dont l'en-tête "kid" est l'Application ID. Voir get_token().

Flux d'autorisation (voir bank.py) :
  1. POST /auth       -> URL de la banque où envoyer la personne
  2. la banque la renvoie vers redirect_url avec ?code=...&state=...
  3. POST /sessions   -> session_id + liste des comptes autorisés (uid)
  4. GET /accounts/{uid}/balances et /transactions
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import jwt


class EnableBankingError(RuntimeError):
    """Levée quand l'API Enable Banking (ou son authentification) échoue."""


class EnableBankingClient:
    BASE_URL = "https://api.enablebanking.com"

    def __init__(self, app_id: str, private_key_path: str, redirect_url: str, valid_days: int = 179) -> None:
        self.app_id = app_id
        self.private_key_path = Path(private_key_path)
        self.redirect_url = redirect_url
        # Le maximum accepté par les banques est 180 jours (voir
        # maximum_consent_validity de GET /aspsps) : 179 pour rester en dessous.
        self.valid_days = valid_days

    def get_token(self) -> str:
        """JWT de l'application (valable 1 h, recalculé à chaque requête :
        peu coûteux, évite de gérer une expiration)."""
        try:
            private_key = self.private_key_path.read_bytes()
        except OSError as exc:
            raise EnableBankingError("Clé privée Enable Banking illisible sur le serveur") from exc
        now = int(time.time())
        return jwt.encode(
            {"iss": "enablebanking.com", "aud": "api.enablebanking.com", "iat": now, "exp": now + 3600},
            private_key,
            algorithm="RS256",
            headers={"kid": self.app_id},
        )

    def _request(self, method: str, path: str, **kwargs) -> dict:
        try:
            response = httpx.request(
                method,
                f"{self.BASE_URL}{path}",
                headers={"Authorization": f"Bearer {self.get_token()}"},
                timeout=30,
                **kwargs,
            )
        except httpx.HTTPError as exc:
            raise EnableBankingError(f"Enable Banking injoignable : {exc}") from exc
        if response.status_code >= 400:
            try:
                detail = response.json().get("message") or response.text
            except ValueError:
                detail = response.text
            raise EnableBankingError(f"Enable Banking {response.status_code} : {detail[:300]}")
        return response.json()

    def list_banks(self, country: str = "FR") -> list[dict]:
        """Les banques du pays : [{"name", "country", "psu_types"}]."""
        return [
            {"name": b["name"], "country": b.get("country", country), "psu_types": b.get("psu_types") or ["personal"]}
            for b in self._request("GET", "/aspsps", params={"country": country}).get("aspsps", [])
        ]

    def start_authorization(self, state: str, bank: str, country: str, psu_type: str) -> str:
        """Démarre l'autorisation chez la banque ; retourne l'URL où envoyer
        la personne. `state` revient tel quel à redirect_url (il dit quelle
        organisation revient, et protège contre les faux retours)."""
        valid_until = datetime.now(UTC) + timedelta(days=self.valid_days)
        data = self._request(
            "POST",
            "/auth",
            json={
                "access": {"valid_until": valid_until.strftime("%Y-%m-%dT%H:%M:%SZ")},
                "aspsp": {"name": bank, "country": country},
                "state": state,
                "redirect_url": self.redirect_url,
                "psu_type": psu_type,
                "language": "fr",
            },
        )
        return data["url"]

    def create_session(self, code: str) -> dict:
        """Échange le code reçu au retour de la banque contre une session
        (session_id, accounts, access.valid_until...)."""
        return self._request("POST", "/sessions", json={"code": code})

    def get_balances(self, account_uid: str) -> list[dict]:
        return self._request("GET", f"/accounts/{account_uid}/balances").get("balances", [])

    def get_transactions(self, account_uid: str, date_from: str, continuation_key: str | None = None) -> dict:
        params = {"date_from": date_from}
        if continuation_key:
            params["continuation_key"] = continuation_key
        return self._request("GET", f"/accounts/{account_uid}/transactions", params=params)
