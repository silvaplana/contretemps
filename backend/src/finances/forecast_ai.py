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
import re
from dataclasses import dataclass

import anthropic

from .ai import DEFAULT_MODEL, MODELS, AnalysisError, cost_usd
from . import forecast_data
from .sandbox import FormulaError, execute

INSTRUCTIONS = """Tu es le trésorier bénévole d'une association.
Tu prépares un prévisionnel : la liste des opérations futures sur les comptes de l'association (tous ses comptes ensemble), de la date de départ jusqu'à la fin de la saison. L'application en tire le solde semaine par semaine (le graphique) et montre ces opérations au lecteur (le tableau) pour qu'il puisse vérifier chaque chiffre.

Tu ne calcules pas toi-même le résultat : tu écris une formule en Python que l'application exécute, puis rejoue à chaque fois que le trésorier bouge un curseur.

La formule :
- définit une fonction prevoir(donnees, p) qui renvoie la liste des opérations prévues, chacune sous la forme {"date": "AAAA-MM-JJ", "libelle": ..., "categorie": ..., "montant": ..., "hypothese": "H1", "sur": False} ; date strictement après donnees["dateDepart"] et au plus donnees["finSaison"] ; montant en euros, recette positive, dépense négative ; virements entre les comptes de l'association exclus ;
- ne compte pas ce qui est déjà dans donnees["soldeDepart"] (solde réel à la date de départ) : ce qui est déjà passé sur le mois en cours est dans moisEnCours ;
- lit les paramètres réglables dans le dictionnaire p (clés déclarées dans "parametres") ;
- n'utilise que Python standard : seuls les modules math et datetime peuvent être importés ; pas de fichier, pas de réseau, pas de print, pas de nom ni d'attribut commençant par « _ », pas de méthode .format() (utilise des f-strings) ;
- reste simple et lisible par un trésorier : des commentaires en français, pas d'astuce.

Les données (dictionnaire donnees, montants en euros, recettes positives, dépenses négatives, virements entre les comptes de l'association exclus) :
- saison, debutSaison, finSaison, dateDepart (AAAA-MM-JJ), soldeDepart, soldeDebutSaison ;
- semaines : [{"date", "mois_commences"}] : les dates du graphique, pour information ;
- moisEnCours : {"mois", "dejaPasseParCategorie"} : ce qui est déjà passé sur le mois de la date de départ (pour ne pas compter deux fois un salaire déjà payé) ;
- moyennesMensuelles : moyenne par mois, par catégorie, des 12 mois avant la date de départ ;
- douzeDerniersMois : [{"mois", "parCategorie"}] : le détail de ces 12 mois (saisonnalité : inscriptions en septembre-octobre, etc.) ;
- operations12Mois : [{"date", "libelle", "categorie", "montant"}] : les opérations de ces 12 mois, une par une ;
- helloAsso : null, ou l'argent HelloAsso qui arrivera sur le compte (voir plus bas) ;
- adherents : null.

Hypothèses : chaque opération repose sur une hypothèse que tu déclares dans "hypotheses" (code "H1", "H2"…, une phrase simple en français). Cherche dans les données, au cas par cas, les rythmes de cette association : le calendrier des échéances, le jour où une plateforme de paiement vire l'argent sur le compte, les dépenses fixes (salaires, loyer, assurance), la saison des inscriptions, les subventions. Chaque hypothèse cite sa preuve (« H2 : loyer de 250 € le 15 de chaque mois, comme sur les 12 derniers mois »). Une hypothèse qui dépend d'un curseur écrit sa valeur entre accolades avec le nom du paramètre (« Salaire du prof : {salaire} € par mois ») : l'application la remplace par la position du curseur.

Paramètres : déclare dans "parametres" chaque paramètre que les consignes du trésorier rendent réglable (nom de clé Python, libellé court en français, min, max, défaut, pas, unité). Respecte les bornes et défauts des consignes. S'il n'en demande aucun, propose 2 ou 3 paramètres utiles.

Explication : 3 à 6 phrases en français simple qui disent ce que fait la formule, poste par poste, pour que le trésorier vérifie que tu as compris sa demande.
"""

# Ajouté seulement quand l'école a HelloAsso relié (spec financier.md §6.4).
HELLOASSO = """
HelloAsso : l'argent HelloAsso donné dans donnees["helloAsso"] est sûr, compte-le en entier et une seule fois : les échéances à venir (echeancesAVenir : date du paiement, montant, nombre d'adhérents, numéro de l'échéance) et encaisseNonVerse (déjà payé par les adhérents, pas encore versé à l'association). Les opérations qui portent cet argent ont "sur": True, et leur total doit faire exactement totalSur ; toutes les autres ont "sur": False. HelloAsso ne verse pas le jour du paiement : il vire une fois par mois, à un jour que tu retrouves dans operations12Mois (libellés contenant HELLOASSO) ; place chaque somme au virement suivant, dans la saison (sinon au dernier jour de la saison), et dis-le dans une hypothèse. Les paiements en plusieurs fois tombent à des dates fixes, à retrouver dans les échéances à venir. Ne compte pas les impayés ni les adhésions résiliées (nonComptes).
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "code": {"type": "string", "description": "Code Python complet définissant prevoir(donnees, p)."},
        "explication": {"type": "string"},
        "hypotheses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "« H1 », « H2 »…"},
                    "texte": {"type": "string"},
                },
                "required": ["code", "texte"],
                "additionalProperties": False,
            },
        },
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
    "required": ["code", "explication", "hypotheses", "parametres"],
    "additionalProperties": False,
}


@dataclass
class Formula:
    code: str
    explanation: str
    parameters: list[dict]  # [{"name", "label", "min", "max", "default", "step", "unit"}]
    hypotheses: list[dict]  # [{"code", "text"}]
    operations: list[dict]  # résultat avec les valeurs par défaut (forecast_data.operations)
    model: str  # clé de MODELS
    served_by: str
    cost: float  # dollars, toutes les tentatives


def _hypotheses(raw: list[dict]) -> list[dict]:
    """Hypothèses déclarées par le modèle : codes « H1 »… uniques."""
    result = []
    for h in raw:
        code = str(h.get("code", "")).strip()
        if not re.fullmatch(r"H\d{1,3}", code) or any(r["code"] == code for r in result):
            raise FormulaError(f"Code d'hypothèse invalide : {code!r} (« H1 », « H2 »…, chacun une fois)")
        result.append({"code": code, "text": str(h.get("texte", "")).strip()})
    return result


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
        # Le paragraphe HelloAsso seulement quand l'école a HelloAsso relié.
        system = INSTRUCTIONS + (HELLOASSO if data.get("helloAsso") is not None else "")
        text = "Données (JSON) :\n" + json.dumps(data, ensure_ascii=False, indent=1)
        text += "\n\nDemande du trésorier pour ce prévisionnel :\n" + (prompt.strip() or "(aucune consigne particulière)")
        messages: list[dict] = [{"role": "user", "content": text}]
        cost = 0.0
        for attempt in range(self.ATTEMPTS):
            try:
                response = self._call(model, messages, system)
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
                hypotheses = _hypotheses(result.get("hypotheses", []))
                code = result["code"]
                operations = forecast_data.operations(
                    execute(code, data, defaults(parameters)), data, {h["code"] for h in hypotheses}
                )
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
                hypotheses=hypotheses,
                operations=operations,
                model=model,
                served_by=response.model or model,
                cost=cost,
            )
        raise AnalysisError("La formule ne fonctionne pas.", cost)  # pragma: no cover

    def _call(self, model: str, messages: list[dict], system: str = INSTRUCTIONS):
        params = {
            "model": model,
            "max_tokens": 32000,
            "system": system,
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
