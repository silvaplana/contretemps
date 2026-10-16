"""Contenu d'un fichier de l'appli (spec fichier-de-base.md §6) : contrôle du
JSON de blocs et des réponses. Fonctions pures, sans base.

Le contenu suit la forme des blocs de BlockNote, l'éditeur utilisé par
l'appli, pour n'avoir aucune conversion :

    {"schema": 1,
     "entry":  {"blocks": [...]},   # formulaire d'entrée
     "result": {"blocks": [...]}}   # formulaire de résultat (vide = automatique)

Un bloc : {"id", "type", "props": {...}, "content": [...], "children": [...]}.
Une question est un bloc dont le type est dans QUESTION_TYPES ; son `id`
(stable, donné par BlockNote) range les réponses (§6.1). Jamais de HTML :
le texte est une liste de morceaux {"type": "text", "text", "styles"} ou de
liens, rendus par React.
"""

from __future__ import annotations

import json
import re
from datetime import date

SCHEMA = 1
MAX_CONTENT_BYTES = 300_000
MAX_DEPTH = 3

# Mise en page, dans tous les fichiers (types BlockNote).
LAYOUT_TYPES = {
    "paragraph", "heading", "quote", "bulletListItem", "numberedListItem", "checkListItem", "divider",
}
# Questions : Questionner et Agir.
QUESTION_TYPES = {"shortText", "longText", "choice", "date", "number", "yesNo", "signature"}
# Blocs qui écrivent dans l'appli : Agir seulement.
ACT_TYPES = {"member", "payment"}
# Blocs du formulaire de résultat.
RESULT_TYPES = {"responseCount", "responseTable", "choiceChart", "total"}

FAMILY_ENTRY_TYPES = {
    "inform": LAYOUT_TYPES,
    "question": LAYOUT_TYPES | QUESTION_TYPES,
    "act": LAYOUT_TYPES | QUESTION_TYPES | ACT_TYPES,
}

TYPE_LABELS = {
    "shortText": "Réponse courte", "longText": "Réponse longue", "choice": "Choix", "date": "Date",
    "number": "Nombre", "yesNo": "Oui / non", "signature": "Signature",
    "member": "Coordonnées", "payment": "Paiement",
}

MEMBER_FIELDS = ("last_name", "first_name", "email", "phone")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SIGNATURE = re.compile(r"^data:image/png;base64,[A-Za-z0-9+/=]+$")
MAX_SIGNATURE = 200_000


class ContentError(ValueError):
    """Contenu ou réponse refusé ; le message est affiché tel quel."""


def empty_content() -> dict:
    return {"schema": SCHEMA, "entry": {"blocks": []}, "result": {"blocks": []}}


def _walk(blocks: list[dict]):
    for bloc in blocks:
        yield bloc
        yield from _walk(bloc.get("children") or [])


def questions(content: dict) -> list[dict]:
    """Les questions du formulaire d'entrée, dans l'ordre de la page."""
    return [b for b in _walk(content.get("entry", {}).get("blocks", [])) if b["type"] in QUESTION_TYPES | ACT_TYPES]


def _check_inline(contenu, chemin: str) -> None:
    if isinstance(contenu, str):
        return
    if not isinstance(contenu, list):
        raise ContentError(f"{chemin} : texte mal formé")
    for morceau in contenu:
        if not isinstance(morceau, dict) or morceau.get("type") not in ("text", "link"):
            raise ContentError(f"{chemin} : texte mal formé")
        if morceau["type"] == "link":
            href = str(morceau.get("href", ""))
            if not href.startswith(("https://", "http://", "mailto:")):
                raise ContentError("Seuls les liens web (https://…) et les adresses email sont acceptés.")
            _check_inline(morceau.get("content", []), chemin)
        elif not isinstance(morceau.get("text", ""), str):
            raise ContentError(f"{chemin} : texte mal formé")


def _check_block(bloc, permis: set[str], profondeur: int, ids: set[str]) -> None:
    if not isinstance(bloc, dict):
        raise ContentError("Bloc mal formé")
    ident, genre = bloc.get("id"), bloc.get("type")
    if not isinstance(ident, str) or not ident or len(ident) > 64:
        raise ContentError("Bloc sans identifiant")
    if ident in ids:
        raise ContentError("Deux blocs ont le même identifiant")
    ids.add(ident)
    if genre not in permis:
        if genre in ACT_TYPES:
            raise ContentError(f"Le bloc « {TYPE_LABELS[genre]} » n'existe que dans un fichier Agir.")
        if genre in QUESTION_TYPES:
            raise ContentError(f"Le bloc « {TYPE_LABELS[genre]} » n'existe pas dans un fichier Informer.")
        raise ContentError(f"Bloc inconnu : {genre}")
    props = bloc.get("props", {})
    if not isinstance(props, dict) or any(
        not isinstance(v, (str, int, float, bool)) and v is not None for v in props.values()
    ):
        raise ContentError("Réglages de bloc mal formés")
    _check_inline(bloc.get("content", []), TYPE_LABELS.get(genre, "Texte"))
    if genre == "choice" and not _options(bloc):
        raise ContentError("Une question à choix doit avoir au moins un choix.")
    if genre == "payment":
        montant = props.get("amount")
        if not isinstance(montant, (int, float)) or isinstance(montant, bool) or not 0 < montant <= 10_000:
            raise ContentError("Le montant d'un paiement doit être compris entre 0 et 10 000 €.")
    enfants = bloc.get("children", [])
    if not isinstance(enfants, list):
        raise ContentError("Bloc mal formé")
    if enfants and profondeur >= MAX_DEPTH:
        raise ContentError("Trop de niveaux de blocs imbriqués")
    for enfant in enfants:
        _check_block(enfant, permis, profondeur + 1, ids)


def _options(bloc: dict) -> list[str]:
    brut = (bloc.get("props") or {}).get("options") or ""
    return [o.strip() for o in str(brut).split("\n") if o.strip()]


def check_content(content, family: str) -> dict:
    """Renvoie le contenu normalisé, ou lève ContentError."""
    if not isinstance(content, dict):
        raise ContentError("Contenu mal formé")
    if len(json.dumps(content, ensure_ascii=False).encode()) > MAX_CONTENT_BYTES:
        raise ContentError("Ce fichier est trop long. Découpez-le en plusieurs fichiers.")
    if family not in FAMILY_ENTRY_TYPES:
        raise ContentError("Nature inconnue")
    entree = (content.get("entry") or {}).get("blocks", [])
    resultat = (content.get("result") or {}).get("blocks", [])
    if not isinstance(entree, list) or not isinstance(resultat, list):
        raise ContentError("Contenu mal formé")
    ids: set[str] = set()
    for bloc in entree:
        _check_block(bloc, FAMILY_ENTRY_TYPES[family], 0, ids)
    if family == "inform" and resultat:
        raise ContentError("Un fichier Informer n'a pas de formulaire de résultat.")
    for bloc in resultat:
        _check_block(bloc, LAYOUT_TYPES | RESULT_TYPES, 0, ids)
    return {"schema": SCHEMA, "entry": {"blocks": entree}, "result": {"blocks": resultat}}


def drop_for_family(content: dict, family: str) -> dict:
    """Le contenu sans les blocs qui n'existent pas dans cette nature
    (changement de nature, fichier-de-base.md §1)."""
    permis = FAMILY_ENTRY_TYPES[family]

    def garder(blocs):
        return [{**b, "children": garder(b.get("children") or [])} for b in blocs if b["type"] in permis]

    return {
        "schema": SCHEMA,
        "entry": {"blocks": garder(content.get("entry", {}).get("blocks", []))},
        "result": {"blocks": [] if family == "inform" else content.get("result", {}).get("blocks", [])},
    }


def _label(bloc: dict) -> str:
    return str((bloc.get("props") or {}).get("label") or TYPE_LABELS.get(bloc["type"], "Question"))


def check_values(content: dict, values, test: bool) -> dict:
    """Contrôle une réponse au formulaire d'entrée ; renvoie les valeurs
    gardées (rien d'inconnu). Une réponse invalide est refusée en entier."""
    if not isinstance(values, dict):
        raise ContentError("Réponse mal formée")
    qs = questions(content)
    connues = {q["id"] for q in qs}
    if set(values) - connues:
        raise ContentError("Cette réponse ne correspond plus au formulaire. Rechargez la page.")
    gardees = {}
    for q in qs:
        valeur = values.get(q["id"])
        vide = valeur is None or valeur == "" or valeur == [] or valeur == {}
        if vide:
            if (q.get("props") or {}).get("required") and q["type"] != "payment":
                raise ContentError(f"Répondez à « {_label(q)} ».")
            continue
        gardees[q["id"]] = _check_value(q, valeur, test)
    return gardees


def _check_value(q: dict, v, test: bool):
    genre, nom = q["type"], _label(q)
    if genre in ("shortText", "longText"):
        limite = 500 if genre == "shortText" else 5000
        if not isinstance(v, str) or len(v) > limite:
            raise ContentError(f"« {nom} » : texte trop long (au plus {limite} caractères).")
        return v.strip()
    if genre == "choice":
        options = _options(q)
        choisis = v if isinstance(v, list) else [v]
        if not (q.get("props") or {}).get("multiple") and len(choisis) > 1:
            raise ContentError(f"« {nom} » : un seul choix possible.")
        if any(c not in options for c in choisis):
            raise ContentError(f"« {nom} » : ce choix n'existe pas.")
        return choisis if (q.get("props") or {}).get("multiple") else choisis[0]
    if genre == "date":
        try:
            date.fromisoformat(str(v))
        except ValueError:
            raise ContentError(f"« {nom} » : date invalide.") from None
        return str(v)
    if genre == "number":
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ContentError(f"« {nom} » : un nombre est attendu.")
        return v
    if genre == "yesNo":
        if not isinstance(v, bool):
            raise ContentError(f"« {nom} » : répondez oui ou non.")
        return v
    if genre == "signature":
        if not isinstance(v, str) or len(v) > MAX_SIGNATURE or not SIGNATURE.match(v):
            raise ContentError(f"« {nom} » : signature illisible, recommencez.")
        return v
    if genre == "member":
        if not isinstance(v, dict) or set(v) - set(MEMBER_FIELDS):
            raise ContentError(f"« {nom} » : coordonnées mal formées.")
        champs = {k: str(v.get(k, "")).strip()[:200] for k in MEMBER_FIELDS if v.get(k)}
        if (q.get("props") or {}).get("required") and not (champs.get("last_name") and champs.get("email")):
            raise ContentError(f"« {nom} » : le nom et l'email sont obligatoires.")
        if champs.get("email") and not EMAIL.match(champs["email"]):
            raise ContentError(f"« {nom} » : adresse email invalide.")
        return champs
    if genre == "payment":
        # Le paiement réel (HelloAsso) viendra avec la diffusion ; en essai,
        # on note seulement le montant, rien n'est payé.
        if not test:
            raise ContentError("Le paiement en ligne n'est pas encore branché.")
        return {"amount": (q.get("props") or {}).get("amount"), "test": True}
    raise ContentError("Question inconnue")


def _inline_text(contenu) -> str:
    morceaux = []
    for m in contenu or []:
        if not isinstance(m, dict):
            continue
        if m.get("type") == "link":
            texte = _inline_text(m.get("content"))
            href = str(m.get("href") or "")
            morceaux.append(f"{texte} ({href})" if href and href != texte else texte or href)
        else:
            morceaux.append(str(m.get("text") or ""))
    return "".join(morceaux)


def readable(content: dict, intro_only: bool) -> list[str]:
    """Version lisible du formulaire d'entrée, un paragraphe par ligne (email
    de diffusion, fichier-de-base.md §2.3) : tout le texte pour un fichier à
    lire ; avec `intro_only`, le texte qui précède la première question (la
    suite se remplit en ligne)."""
    lignes: list[str] = []
    numero = 0
    for bloc in _walk(content.get("entry", {}).get("blocks", [])):
        genre = bloc.get("type")
        if genre in QUESTION_TYPES | ACT_TYPES:
            if intro_only:
                break
            continue
        if genre == "divider":
            continue
        texte = _inline_text(bloc.get("content")).strip()
        if not texte:
            continue
        if genre == "numberedListItem":
            numero += 1
            texte = f"{numero}. {texte}"
        else:
            numero = 0
            if genre == "bulletListItem":
                texte = f"• {texte}"
            elif genre == "checkListItem":
                texte = ("☑ " if (bloc.get("props") or {}).get("checked") else "☐ ") + texte
        lignes.append(texte)
    return lignes
