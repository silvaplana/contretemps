"""Les règles en français des options (spec/core.md §9.2, étape 7c) :
« Enlever 10 € par année d'ancienneté, 50 € maximum ». L'assistant la
reformule (« Compris : … ») et l'écrit en un calcul court, gardé en base ;
c'est le calcul qui donne le montant, jamais l'assistant.

Le calcul est une seule expression Python, vérifiée nœud par nœud
(`evaluate`) : des nombres, les variables de `VARIABLES`, + − × ÷,
comparaisons, « si … sinon … », min, max, abs, round. Rien d'autre ne
s'exécute.

Sans clé (`ANTHROPIC_API_KEY`), le bouton répond que l'assistant n'est pas
disponible.
"""

from __future__ import annotations

import ast
import datetime as dt
import logging
import operator
import os
from collections.abc import Callable

import anthropic
from comptes import Compte
from members import values as member_values
from pydantic import BaseModel
from saisons import Saison
from saisons.portee import toutes_saisons
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Ce que le calcul sait d'un membre (noms en français : ils s'affichent sous
# la règle, comme dans la maquette).
VARIABLES = {
    "prix": "le tarif de la formule choisie, en euros",
    "age": "l'âge de la personne au début de la saison, en années",
    "annees_anciennete": "le nombre de saisons d'avant où la personne était déjà inscrite (0 la première année)",
    "nb_famille": "le nombre de personnes de sa famille inscrites cette saison, elle comprise",
}
_EXEMPLE = {"prix": 300.0, "age": 30, "annees_anciennete": 2, "nb_famille": 2}

MODELE = "claude-opus-5-5"
PRIX_PAR_MODELE = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-opus-4-8": (5.0, 25.0),
}

CONSIGNE = """Tu aides le bureau d'une association à écrire une règle de tarif.
On te donne une règle écrite en français, par exemple « Enlever 10 € par année d'ancienneté, \
50 € maximum ». Tu renvoies :
- `compris` : la règle redite en une phrase courte et claire, en français simple, pour que la \
personne vérifie que tu l'as bien comprise (ex. « −10 € par année depuis la première inscription, \
50 € au plus. »).
- `calcul` : une seule expression Python qui donne le montant en euros à ajouter au tarif : \
négative pour une réduction, positive pour un supplément, 0 quand la règle ne s'applique pas \
(ex. « -min(10 * annees_anciennete, 50) », « -prix * 0.5 if age < 12 else 0 »).

Le calcul n'utilise que ces variables :
{variables}
et seulement : des nombres, + - * / // %, des comparaisons, and, or, not, « a if condition else b », \
min, max, abs, round. Pas d'autre nom, pas d'appel, pas d'import.

Si la règle demande une information que ces variables n'ont pas, mets `calcul` à "" et explique \
dans `compris` ce qui manque."""


class RuleError(ValueError):
    """Message lisible, renvoyé tel quel à l'écran."""


# --- Le calcul ---

_OPERATEURS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.USub: operator.neg, ast.UAdd: operator.pos, ast.Not: operator.not_,
    ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
    ast.Eq: operator.eq, ast.NotEq: operator.ne,
}
_FONCTIONS = {"min": min, "max": max, "abs": abs, "round": round}


def _valeur(noeud: ast.AST, variables: dict):
    match noeud:
        case ast.Constant(value=v) if isinstance(v, int | float) and not isinstance(v, bool):
            return v
        case ast.Name(id=nom) if nom in VARIABLES:
            if variables.get(nom) is None:
                raise LookupError(nom)
            return variables[nom]
        case ast.BinOp(left=a, op=op, right=b) if type(op) in _OPERATEURS:
            return _OPERATEURS[type(op)](_valeur(a, variables), _valeur(b, variables))
        case ast.UnaryOp(op=op, operand=a) if type(op) in _OPERATEURS:
            return _OPERATEURS[type(op)](_valeur(a, variables))
        case ast.BoolOp(op=ast.And(), values=termes):
            return all(_valeur(t, variables) for t in termes)
        case ast.BoolOp(op=ast.Or(), values=termes):
            return any(_valeur(t, variables) for t in termes)
        case ast.Compare(left=gauche, ops=ops, comparators=droites) if all(type(o) in _OPERATEURS for o in ops):
            a = _valeur(gauche, variables)
            for op, droite in zip(ops, droites):
                b = _valeur(droite, variables)
                if not _OPERATEURS[type(op)](a, b):
                    return False
                a = b
            return True
        case ast.IfExp(test=si, body=alors, orelse=sinon):
            return _valeur(alors if _valeur(si, variables) else sinon, variables)
        case ast.Call(func=ast.Name(id=nom), args=args, keywords=[]) if nom in _FONCTIONS and args:
            return _FONCTIONS[nom](*(_valeur(a, variables) for a in args))
    raise RuleError(f"Calcul refusé : « {ast.unparse(noeud)} »")


def evaluate(calculation: str, variables: dict) -> int | None:
    """Le montant en centimes (négatif = en moins), ou None quand la fiche
    n'a pas une information dont le calcul a besoin (âge inconnu…)."""
    try:
        arbre = ast.parse(calculation.strip(), mode="eval")
    except SyntaxError as erreur:
        raise RuleError("Calcul illisible") from erreur
    try:
        return round(float(_valeur(arbre.body, variables)) * 100)
    except LookupError:
        return None
    except (ArithmeticError, TypeError, ValueError) as erreur:
        if isinstance(erreur, RuleError):
            raise
        raise RuleError(f"Calcul impossible : {erreur}") from erreur


def check(calculation: str) -> str:
    """Le calcul nettoyé, s'il est accepté (sinon RuleError)."""
    calculation = calculation.strip()
    if not calculation or len(calculation) > 500:
        raise RuleError("Calcul vide ou trop long")
    evaluate(calculation, _EXEMPLE)
    return calculation


# --- Ce que le calcul sait des membres ---


def members(db: Session, org_id: int, season_id: int) -> list[tuple[Compte, dict]]:
    """Les membres de la saison, avec leurs variables (sauf `prix`)."""
    saison = db.get(Saison, season_id)
    with toutes_saisons(db):
        tous = {c.id: c for c in db.scalars(select(Compte).where(Compte.ecole_id == org_id))}
    fiches = sorted((c for c in tous.values() if c.saison_id == season_id), key=lambda c: (c.nom, c.prenom))
    familles: dict[int, int] = {}
    for c in fiches:
        if c.famille_id is not None:
            familles[c.famille_id] = familles.get(c.famille_id, 0) + 1
    connues = member_values.known_values(db, org_id, season_id)
    resultat = []
    for c in fiches:
        anciennete, avant = 0, tous.get(c.compte_precedent_id)
        while avant is not None and anciennete < 100:
            anciennete += 1
            avant = tous.get(avant.compte_precedent_id)
        naissance = member_values.birth_date(connues.get(c.id, {}))
        age = None
        if naissance is not None:
            debut = saison.date_debut
            age = debut.year - naissance.year - ((debut.month, debut.day) < (naissance.month, naissance.day))
        resultat.append((c, {
            "age": age, "annees_anciennete": anciennete,
            "nb_famille": familles.get(c.famille_id, 1) if c.famille_id is not None else 1,
        }))
    return resultat


def _euros(centimes: int) -> str:
    texte = f"{abs(centimes) / 100:.2f}".replace(".", ",").removesuffix(",00")
    return f"{'+' if centimes > 0 else '−' if centimes < 0 else ''}{texte} €"


def example(db: Session, org_id: int, season_id: int, calculation: str, plan: tuple[str, int] | None) -> str | None:
    """« Léa Martin, 3 ans d'ancienneté → −30 €. » sur un vrai membre de la
    saison, de préférence un à qui la règle s'applique. `plan` : la formule
    prise pour `prix` (nom, centimes)."""
    utilisees = {n.id for n in ast.walk(ast.parse(calculation, mode="eval")) if isinstance(n, ast.Name)}
    premier = None
    for compte, variables in members(db, org_id, season_id):
        variables["prix"] = plan[1] / 100 if plan else None
        montant = evaluate(calculation, variables)
        if montant is None:
            continue
        morceaux = [f"{compte.prenom} {compte.nom}".strip()]
        if "age" in utilisees:
            morceaux.append(f"{variables['age']} ans")
        if "annees_anciennete" in utilisees:
            n = variables["annees_anciennete"]
            morceaux.append(f"{n} an{'s' if n > 1 else ''} d’ancienneté")
        if "nb_famille" in utilisees:
            morceaux.append(f"famille de {variables['nb_famille']}")
        if "prix" in utilisees and plan:
            morceaux.append(plan[0])
        texte = f"{', '.join(morceaux)} → {_euros(montant) if montant else 'ne s’applique pas'}."
        if montant:
            return texte
        premier = premier or texte
    return premier


# --- L'assistant ---


class RuleJson(BaseModel):
    compris: str
    calcul: str


def cout_usd(modele: str, jetons_entree: int, jetons_sortie: int) -> float:
    entree, sortie = PRIX_PAR_MODELE.get(modele, PRIX_PAR_MODELE[MODELE])
    return round((jetons_entree * entree + jetons_sortie * sortie) / 1_000_000, 4)


class RuleReader:
    # La 2e tentative reçoit l'erreur de la 1re pour corriger le calcul.
    ATTEMPTS = 2

    def __init__(
        self,
        noter_cout: Callable[[Session, int, float, str], None] | None = None,
        plafond_atteint: Callable[[Session, int], bool] | None = None,
        client: anthropic.Anthropic | None = None,
    ) -> None:
        self.noter_cout = noter_cout
        self.plafond_atteint = plafond_atteint
        self._client = client

    def understand(self, db: Session, org_id: int, rule: str) -> tuple[str, str]:
        """(« Compris : … », calcul vérifié). Calcul vide : la règle demande
        une information que l'appli n'a pas, `compris` dit laquelle."""
        if self._client is None and not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuleError("L'assistant n'est pas disponible.")
        if self.plafond_atteint is not None and self.plafond_atteint(db, org_id):
            raise RuleError("Le plafond mensuel de l'assistant est atteint.")
        if self._client is None:
            self._client = anthropic.Anthropic()
        variables = "\n".join(f"- {nom} : {sens}" for nom, sens in VARIABLES.items())
        messages = [{"role": "user", "content": f"Règle : {rule.strip()}"}]
        for tentative in range(self.ATTEMPTS):
            try:
                reponse = self._client.beta.messages.parse(
                    model=MODELE,
                    max_tokens=4000,
                    system=CONSIGNE.format(variables=variables),
                    messages=messages,
                    output_config={"effort": "low"},
                    output_format=RuleJson,
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks="default",
                )
            except anthropic.APIError as erreur:
                logger.exception("Règle de tarif : appel refusé")
                raise RuleError("L'assistant n'a pas pu lire la règle : réessayez.") from erreur
            if self.noter_cout is not None:
                self.noter_cout(
                    db, org_id, cout_usd(reponse.model, reponse.usage.input_tokens, reponse.usage.output_tokens),
                    reponse.model,
                )
            lu = reponse.parsed_output
            if reponse.stop_reason == "refusal" or lu is None:
                raise RuleError("L'assistant n'a pas pu lire la règle : reformulez-la.")
            if not lu.calcul.strip():
                return lu.compris.strip(), ""
            try:
                return lu.compris.strip(), check(lu.calcul)
            except RuleError as erreur:
                if tentative + 1 == self.ATTEMPTS:
                    raise RuleError("L'assistant n'a pas su écrire le calcul : reformulez la règle.") from erreur
                messages += [
                    {"role": "assistant", "content": lu.model_dump_json()},
                    {"role": "user", "content": f"Ton calcul a été refusé : {erreur}. Corrige-le."},
                ]
        raise RuleError("L'assistant n'a pas su écrire le calcul.")  # pragma: no cover
