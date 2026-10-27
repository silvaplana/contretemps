"""Les appels à l'API HelloAsso v5 dont la connexion a besoin, repris de
Sambo Admin (`helloasso/helloasso.py`) : jeton OAuth2 « client
credentials », l'association reliée aux clés, ses formulaires.
Sandbox (`api.helloasso-sandbox.com`) avec HELLOASSO_SANDBOX=1."""

from __future__ import annotations

import os
from dataclasses import dataclass

import requests

PRODUCTION = "https://api.helloasso.com"
SANDBOX = "https://api.helloasso-sandbox.com"
DELAI = 20  # secondes


class HelloAssoError(Exception):
    """Message lisible, affiché tel quel sous « La connexion n'a pas marché »."""


@dataclass
class Organization:
    name: str
    slug: str
    # Titres des formulaires d'adhésion (`Membership`).
    forms: list[str]


def _base() -> str:
    return SANDBOX if os.environ.get("HELLOASSO_SANDBOX") == "1" else PRODUCTION


def _get(path: str, token: str, params: dict | None = None) -> dict | list:
    try:
        reponse = requests.get(
            f"{_base()}{path}", headers={"Authorization": f"Bearer {token}"}, params=params, timeout=DELAI
        )
    except requests.RequestException as erreur:
        raise HelloAssoError("HelloAsso ne répond pas : réessayez dans un moment.") from erreur
    if reponse.status_code in (401, 403):
        raise HelloAssoError("Ces clés n’ont pas accès à l’association : vérifiez leurs droits dans HelloAsso.")
    if not reponse.ok:
        raise HelloAssoError(f"HelloAsso a répondu par une erreur ({reponse.status_code}) : réessayez plus tard.")
    return reponse.json()


def connect(client_id: str, client_secret: str) -> Organization:
    """Demande un jeton avec ces clés, puis lit l'association et ses
    formulaires d'adhésion. HelloAssoError si quelque chose ne va pas."""
    try:
        reponse = requests.post(
            f"{_base()}/oauth2/token",
            data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret},
            timeout=DELAI,
        )
    except requests.RequestException as erreur:
        raise HelloAssoError("HelloAsso ne répond pas : réessayez dans un moment.") from erreur
    if reponse.status_code in (400, 401, 403):
        raise HelloAssoError(
            "HelloAsso refuse ces clés. Vérifiez qu’elles ont été copiées en entier, sans espace, "
            "depuis Mon compte > Intégrations et API."
        )
    if not reponse.ok:
        raise HelloAssoError(f"HelloAsso a répondu par une erreur ({reponse.status_code}) : réessayez plus tard.")
    token = reponse.json()["access_token"]
    associations = _get("/v5/users/me/organizations", token)
    if not associations:
        raise HelloAssoError("Ces clés ne sont reliées à aucune association.")
    association = associations[0]
    slug = association["organizationSlug"]
    formulaires = _get(
        f"/v5/organizations/{slug}/forms", token, params={"formTypes": "Membership", "pageSize": 100}
    )
    formulaires = formulaires.get("data", []) if isinstance(formulaires, dict) else formulaires
    return Organization(
        name=association.get("name") or slug,
        slug=slug,
        forms=[f.get("title") or f.get("formSlug", "") for f in formulaires],
    )
