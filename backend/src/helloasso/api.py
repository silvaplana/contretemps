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


def _token(client_id: str, client_secret: str) -> str:
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
    return reponse.json()["access_token"]


def _data(reponse: dict | list) -> list:
    return reponse.get("data", []) if isinstance(reponse, dict) else reponse


def connect(client_id: str, client_secret: str) -> Organization:
    """Demande un jeton avec ces clés, puis lit l'association et ses
    formulaires d'adhésion. HelloAssoError si quelque chose ne va pas."""
    token = _token(client_id, client_secret)
    associations = _get("/v5/users/me/organizations", token)
    if not associations:
        raise HelloAssoError("Ces clés ne sont reliées à aucune association.")
    association = associations[0]
    slug = association["organizationSlug"]
    formulaires = _data(
        _get(f"/v5/organizations/{slug}/forms", token, params={"formTypes": "Membership", "pageSize": 100})
    )
    return Organization(
        name=association.get("name") or slug,
        slug=slug,
        forms=[f.get("title") or f.get("formSlug", "") for f in formulaires],
    )


# Les natures de formulaire proposées comme campagne (spec §3).
CAMPAIGN_TYPES = ("Membership", "Event")


@dataclass
class Form:
    form_type: str
    form_slug: str
    name: str
    # « Public », « Private », « Draft », « Disabled » (état HelloAsso).
    state: str


# Questions HelloAsso (`customFields[].type`) → format de la fiche.
FORMATS = {
    "Date": "date",
    "TextInput": "short_text",
    "FreeText": "long_text",
    "ChoiceList": "list",
    "File": "file",
    "YesNo": "yes_no",
    "Phone": "phone",
    "Zipcode": "postal_code",
    "Number": "number",
}


def forms(client_id: str, client_secret: str, slug: str) -> list[Form]:
    """Les formulaires d'adhésion et d'événement de l'association."""
    token = _token(client_id, client_secret)
    params = {"formTypes": ",".join(CAMPAIGN_TYPES), "pageSize": 100}
    return [
        Form(
            form_type=f.get("formType", ""),
            form_slug=f.get("formSlug", ""),
            name=f.get("title") or f.get("formSlug", ""),
            state=f.get("state", ""),
        )
        for f in _data(_get(f"/v5/organizations/{slug}/forms", token, params=params))
    ]


def form_fields(client_id: str, client_secret: str, slug: str, form_type: str, form_slug: str) -> list[dict]:
    """Les questions du formulaire (toutes formules confondues, sans
    doublon), au format de `members.fields.set_external`."""
    token = _token(client_id, client_secret)
    formulaire = _get(f"/v5/organizations/{slug}/forms/{form_type}/{form_slug}/public", token)
    questions: dict[str, dict] = {}
    for tier in formulaire.get("tiers") or []:
        for question in tier.get("customFields") or []:
            key = str(question.get("id"))
            if key in questions or not (question.get("label") or "").strip():
                continue
            questions[key] = {
                "source_key": key,
                "label": question["label"],
                "required": bool(question.get("isRequired")),
                "format": FORMATS.get(question.get("type"), "short_text"),
                "choices": question.get("values") or None,
            }
    return list(questions.values())
