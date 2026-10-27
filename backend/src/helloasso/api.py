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


# Les lignes d'une commande qui sont une personne inscrite (adhésion,
# billet d'événement) ; les dons et options à part ne font pas de fiche.
PERSON_ITEMS = ("Membership", "Registration")


def orders(client_id: str, client_secret: str, slug: str, form_type: str, form_slug: str) -> list[dict]:
    """Les inscrits de la campagne, un par ligne de commande (une commande
    peut inscrire plusieurs personnes, ex. une fratrie payée par un parent),
    repris de Sambo Admin (`get_members`, `get_member_payments`). Montants en
    centimes."""
    token = _token(client_id, client_secret)
    path = f"/v5/organizations/{slug}/forms/{form_type}/{form_slug}/orders"
    items, page = [], 1
    while True:
        reponse = _get(path, token, params={"pageIndex": page, "pageSize": 100, "withDetails": "true"})
        for order in _data(reponse):
            payer = order.get("payer") or {}
            payments = {p.get("id"): p for p in order.get("payments") or []}
            for item in order.get("items") or []:
                if item.get("type") not in PERSON_ITEMS:
                    continue
                user = item.get("user") or {}
                items.append(
                    {
                        "item_id": str(item.get("id")),
                        "order_id": str(order.get("id")),
                        "first_name": (user.get("firstName") or payer.get("firstName") or "").strip(),
                        "last_name": (user.get("lastName") or payer.get("lastName") or "").strip(),
                        "payer_email": (payer.get("email") or "").strip() or None,
                        "tier_name": item.get("name") or "",
                        "amount": item.get("amount") or 0,
                        "discount_code": (item.get("discount") or {}).get("code"),
                        "state": item.get("state") or "",
                        "order_date": order.get("date"),
                        "answers": [
                            {"id": str(c.get("id")) if c.get("id") is not None else None, "name": c.get("name") or "",
                             "answer": c.get("answer")}
                            for c in item.get("customFields") or []
                        ],
                        "payments": [
                            {
                                "amount": ref.get("shareAmount") or 0,
                                "date": payments[ref.get("id")].get("date"),
                                "state": payments[ref.get("id")].get("state"),
                                "means": payments[ref.get("id")].get("paymentMeans"),
                                "installment": payments[ref.get("id")].get("installmentNumber"),
                            }
                            for ref in item.get("payments") or []
                            if ref.get("id") in payments
                        ],
                    }
                )
        total = (reponse.get("pagination") or {}).get("totalPages", page) if isinstance(reponse, dict) else page
        if page >= total:
            return items
        page += 1
