"""Rédaction de la formule d'un prévisionnel par un modèle de langage (API
Claude, mêmes modèles et même calcul du coût que le bilan : voir ai.py),
repris de Sambo Admin (forecasts/ai.py). Le modèle ne calcule pas le
résultat : il écrit une formule Python (fonction prevoir(donnees, p)) et
déclare ses paramètres réglables (curseurs de l'écran), d'après les
consignes du trésorier.

La formule est vérifiée puis exécutée par l'appli (voir sandbox.py) : en
cas d'échec, le modèle reçoit l'erreur et corrige sa formule (une fois).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import anthropic

from .ai import DEFAULT_MODEL, MODELS, AnalysisError, cost_usd
from .sandbox import FormulaError, run

INSTRUCTIONS = """Tu es le trésorier bénévole d'une association.
Tu prépares un prévisionnel : le solde des comptes de l'association (tous ses comptes cumulés) chaque semaine, de la date de départ jusqu'à la fin de la saison.

Tu ne calcules pas toi-même le résultat : tu écris une formule en Python que l'application exécute, puis rejoue à chaque fois que le trésorier bouge un curseur.

La formule :
- définit une fonction prevoir(donnees, p) qui renvoie une liste avec une valeur par élément de donnees["semaines"], dans le même ordre : le solde prévu (en euros) à la date de cette semaine, sous la forme {"date": ..., "solde": ...} ;
- part de donnees["soldeDepart"] (solde réel à la date de départ) ;
- lit les paramètres réglables dans le dictionnaire p (clés déclarées dans "parametres") ;
- n'utilise que Python standard : seuls les modules math et datetime peuvent être importés ; pas de fichier, pas de réseau, pas de print, pas de nom ni d'attribut commençant par « _ », pas de méthode .format() (utilise des f-strings) ;
- reste simple et lisible par un trésorier : des commentaires en français, pas d'astuce.

Les données (dictionnaire donnees, montants en euros, recettes positives, dépenses négatives, virements entre les comptes de l'association exclus) :
- saison, debutSaison, finSaison, dateDepart (AAAA-MM-JJ), soldeDepart, soldeDebutSaison ;
- semaines : [{"date", "mois_commences"}] ; mois_commences : les mois ("AAAA-MM") dont le 1er jour tombe dans la semaine, utile pour les dépenses mensuelles ;
- moisEnCours : {"mois", "dejaPasseParCategorie"} : ce qui est déjà passé sur le mois de la date de départ (pour ne pas compter deux fois un salaire déjà payé) ;
- moyennesMensuelles : moyenne par mois, par catégorie, des 12 mois avant la date de départ ;
- douzeDerniersMois : [{"mois", "parCategorie"}] : le détail de ces 12 mois (saisonnalité : inscriptions en septembre-octobre, etc.) ;
- adherents : null, ou {"nombre", "majeurs", "mineurs", "prixMoyenAdhesion", "totalAdhesions", "echeancesAVenir": {"AAAA-MM": montant}, "impayes"} : inscrits de la saison en cours et échéances des paiements en plusieurs fois pas encore encaissées.

Paramètres : déclare dans "parametres" chaque paramètre que les consignes du trésorier rendent réglable (nom de clé Python, libellé court en français, min, max, défaut, pas, unité). Respecte les bornes et défauts des consignes. S'il n'en demande aucun, propose 2 ou 3 paramètres utiles.

Explication : 3 à 6 phrases en français simple qui disent ce que fait la formule, poste par poste, pour que le trésorier vérifie que tu as compris sa demande. Si des données manquent (adherents null...), dis comment tu as fait sans.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "code": {"type": "string", "description": "Code Python complet définissant prevoir(donnees, p)."},
        "explication": {"type": "string"},
        "parametres": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "nom": {"type": "string", "description": "Clé dans p (identifiant Python)."},
                    "libelle": {"type": "string"},
                    "min": {"type": "number"},
                    "max": {"type": "number"},
                    "defaut": {"type": "number"},
                    "pas": {"type": "number"},
                    "unite": {"type": "string", "description": "« € », « % », « inscrits »… ou vide."},
                },
                "required": ["nom", "libelle", "min", "max", "defaut", "pas", "unite"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["code", "explication", "parametres"],
    "additionalProperties": False,
}


@dataclass
class Formula:
    code: str
    explanation: str
    parameters: list[dict]  # [{"name", "label", "min", "max", "default", "step", "unit"}]
    balances: list[float]  # résultat avec les valeurs par défaut
    model: str  # clé de MODELS
    served_by: str
    cost: float  # dollars, toutes les tentatives


def defaults(parameters: list[dict]) -> dict:
    return {p["name"]: p["default"] for p in parameters}


def _parameters(raw: list[dict]) -> list[dict]:
    """Paramètres déclarés par le modèle, contrôlés (identifiant, bornes)."""
    result = []
    for p in raw:
        name = str(p.get("nom", "")).strip()
        if not name.isidentifier() or name.startswith("_") or any(r["name"] == name for r in result):
            raise FormulaError(f"Nom de paramètre invalide : {name!r}")
        low, high = float(p["min"]), float(p["max"])
        if low > high:
            low, high = high, low
        step = abs(float(p.get("pas") or 0)) or (high - low) / 100 or 1
        default = min(high, max(low, float(p["defaut"])))
        result.append(
            {
                "name": name,
                "label": str(p.get("libelle") or name).strip(),
                "min": low,
                "max": high,
                "default": default,
                "step": step,
                "unit": str(p.get("unite") or "").strip(),
            }
        )
    return result


class Coder:
    # Tentatives : la 2e reçoit l'erreur de la 1re pour corriger la formule.
    ATTEMPTS = 2

    def __init__(self, client: anthropic.Anthropic | None = None) -> None:
        self._client = client

    def _anthropic(self) -> anthropic.Anthropic:
        if self._client is None:
            self._client = anthropic.Anthropic()
        return self._client

    def write(self, model: str, data: dict, prompt: str) -> Formula:
        """data : données de la formule (voir forecast_data.build) ; prompt :
        consignes du trésorier. La formule rendue a été vérifiée et exécutée
        avec les valeurs par défaut de ses paramètres."""
        if model not in MODELS:
            raise AnalysisError(f"Modèle inconnu : {model}")
        text = "Données (JSON) :\n" + json.dumps(data, ensure_ascii=False, indent=1)
        text += "\n\nDemande du trésorier pour ce prévisionnel :\n" + (prompt.strip() or "(aucune consigne particulière)")
        messages: list[dict] = [{"role": "user", "content": text}]
        cost = 0.0
        for attempt in range(self.ATTEMPTS):
            try:
                response = self._call(model, messages)
            except AnalysisError as exc:
                exc.cost += cost  # la 1re tentative a été facturée
                raise
            cost += cost_usd(response.model or model, response.usage)
            if response.stop_reason == "refusal":
                raise AnalysisError("L'écriture de ce prévisionnel a été refusée.", cost)
            if response.stop_reason == "max_tokens":
                raise AnalysisError("Réponse incomplète (trop longue).", cost)
            answer = next((b.text for b in response.content if b.type == "text"), "")
            try:
                result = json.loads(answer)
                parameters = _parameters(result.get("parametres", []))
                code = result["code"]
                balances = run(code, data, defaults(parameters))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                problem = str(exc) if isinstance(exc, FormulaError) else f"Réponse illisible : {exc}"
                if attempt + 1 == self.ATTEMPTS:
                    raise AnalysisError(f"La formule ne fonctionne pas : {problem}", cost) from exc
                messages += [
                    {"role": "assistant", "content": answer},
                    {"role": "user", "content": f"Ta formule a été refusée ou a échoué : {problem}\nCorrige-la et renvoie la réponse complète."},
                ]
                continue
            return Formula(
                code=code,
                explanation=str(result.get("explication", "")).strip(),
                parameters=parameters,
                balances=balances,
                model=model,
                served_by=response.model or model,
                cost=cost,
            )
        raise AnalysisError("La formule ne fonctionne pas.", cost)  # pragma: no cover

    def _call(self, model: str, messages: list[dict]):
        params = {
            "model": model,
            "max_tokens": 32000,
            "system": INSTRUCTIONS,
            "messages": messages,
            "output_config": {"format": {"type": "json_schema", "schema": SCHEMA}},
        }
        if model != "claude-haiku-5-5":
            # Comme le bilan : si le modèle décline, l'API relance la demande
            # sur le modèle de secours recommandé.
            params["betas"] = ["server-side-fallback-2026-07-01"]
            params["fallbacks"] = "default"
        try:
            with self._anthropic().beta.messages.stream(**params) as stream:
                return stream.get_final_message()
        except Exception as exc:  # toute erreur de l'appel en message clair
            raise AnalysisError(f"L'écriture de la formule a échoué : {exc}") from exc


__all__ = ["DEFAULT_MODEL", "MODELS", "Coder", "Formula", "defaults"]
