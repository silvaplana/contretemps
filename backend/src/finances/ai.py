"""Appel à l'IA (API Claude d'Anthropic) pour un bilan financier, repris de
Sambo Admin (financialreports/ai.py).

L'IA ne calcule rien : le tableau est calculé au centime par l'appli (voir
report.py). Elle reçoit les chiffres de la saison et des saisons
précédentes et :
- classe les opérations de la catégorie « Autres » (catégorie existante ou
  nouvelle) ;
- écrit l'analyse de 5 lignes (faits marquants et comparaisons).

Clé d'API : variable d'environnement ANTHROPIC_API_KEY (lue par le SDK).
Coût : en dollars, comme l'assistant (affiché en euros par l'appli).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import anthropic

# Modèles proposés dans l'écran (mêmes libellés que l'assistant). Prix en
# dollars par million de jetons (entrée, sortie).
MODELS: dict[str, dict] = {
    "claude-haiku-5-5": {"label": "Haiku 5.5", "input": 0.10, "output": 0.50},
    "claude-sonnet-5-5": {"label": "Sonnet 5.5", "input": 2.0, "output": 10.0},
    "claude-opus-5-5": {"label": "Opus 5.5", "input": 4.0, "output": 20.0},
    "claude-fable-5-1": {"label": "Fable 5.1", "input": 10.0, "output": 50.0},
}
DEFAULT_MODEL = "claude-sonnet-5-5"
# Modèles de repli possibles, si le premier décline la demande : pour
# calculer le coût au bon tarif.
_OTHER_PRICES = {"claude-opus-4-8": (5.0, 25.0), "claude-opus-5": (5.0, 25.0), "claude-sonnet-5": (2.0, 10.0)}

# Consignes fixes, complétées par les consignes saisies dans l'écran.
INSTRUCTIONS = """Tu es le trésorier bénévole d'une association.
On te donne le compte d'exploitation d'une saison, calculé par l'application à partir des relevés de banque (tous les comptes de l'association), ainsi que les chiffres des saisons précédentes (soldes, recettes et dépenses par catégorie).

Les chiffres fournis sont exacts au centime : ne recalcule aucun total et n'invente aucun chiffre.

Ta mission :
1. Classer chacune des opérations de la catégorie « Autres » (liste "operationsAClasser") : choisis une des catégories existantes si elle convient, sinon crée une catégorie courte et claire (par exemple « Réception AG »). Laisse « Autres » si rien ne convient vraiment.
2. Écrire une analyse en 5 lignes au plus (une phrase courte par ligne), en français simple, sans jargon comptable, avec des montants arrondis à l'euro :
   - les faits marquants de la saison ;
   - la comparaison avec les saisons précédentes : solde des comptes, principaux postes de recettes et de dépenses.
   Tiens compte de ton classement des opérations « Autres ». Si la saison n'est pas terminée (date d'arrêt avant la fin de saison), dis-le.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "classifications": {
            "type": "array",
            "description": "Une entrée par opération de la liste operationsAClasser.",
            "items": {
                "type": "object",
                "properties": {"operationId": {"type": "integer"}, "category": {"type": "string"}},
                "required": ["operationId", "category"],
                "additionalProperties": False,
            },
        },
        "analysis": {
            "type": "array",
            "description": "Analyse : 5 lignes au plus, une phrase par ligne.",
            "items": {"type": "string"},
        },
    },
    "required": ["classifications", "analysis"],
    "additionalProperties": False,
}


class AnalysisError(Exception):
    """Échec de l'appel à l'IA (clé absente, réseau, refus...) : message
    affichable tel quel. cost : ce que l'appel a quand même coûté ($)."""

    def __init__(self, message: str, cost: float = 0.0) -> None:
        super().__init__(message)
        self.cost = cost


@dataclass
class Analysis:
    classifications: dict[int, str]
    analysis: list[str]
    model: str  # clé de MODELS
    served_by: str  # identifiant du modèle qui a vraiment répondu
    cost: float  # dollars


def cost_usd(model_id: str, usage) -> float:
    if model_id in _OTHER_PRICES:
        input_price, output_price = _OTHER_PRICES[model_id]
    else:
        spec = next((m for key, m in MODELS.items() if model_id.startswith(key)), MODELS[DEFAULT_MODEL])
        input_price, output_price = spec["input"], spec["output"]
    input_tokens = (
        (usage.input_tokens or 0)
        + 1.25 * (getattr(usage, "cache_creation_input_tokens", 0) or 0)
        + 0.1 * (getattr(usage, "cache_read_input_tokens", 0) or 0)
    )
    return (input_tokens * input_price + (usage.output_tokens or 0) * output_price) / 1_000_000


class Analyst:
    def __init__(self, client: anthropic.Anthropic | None = None) -> None:
        self._client = client

    def _anthropic(self) -> anthropic.Anthropic:
        if self._client is None:
            self._client = anthropic.Anthropic()
        return self._client

    def analyze(self, model: str, data: dict, prompt: str) -> Analysis:
        """data : chiffres envoyés à l'IA (voir FinancialReports._ai_data) ;
        prompt : consignes saisies dans l'écran (peut être vide)."""
        if model not in MODELS:
            raise AnalysisError(f"Modèle inconnu : {model}")
        text = "Données de la saison (JSON) :\n" + json.dumps(data, ensure_ascii=False, indent=1)
        if prompt.strip():
            text += "\n\nConsignes du trésorier pour ce bilan :\n" + prompt.strip()
        params = {
            "model": model,
            "max_tokens": 32000,
            "system": INSTRUCTIONS,
            "messages": [{"role": "user", "content": text}],
            "output_config": {"format": {"type": "json_schema", "schema": SCHEMA}},
        }
        if model != "claude-haiku-5-5":
            # Si le modèle refuse la demande (filtres de sécurité), l'API
            # la relance d'elle-même sur le modèle de secours recommandé.
            params["betas"] = ["server-side-fallback-2026-07-01"]
            params["fallbacks"] = "default"
        try:
            with self._anthropic().beta.messages.stream(**params) as stream:
                response = stream.get_final_message()
        except Exception as exc:  # noqa: BLE001 - toute erreur de l'appel (clé absente, réseau...) en message clair
            raise AnalysisError(f"L'analyse a échoué : {exc}") from exc

        cost = cost_usd(response.model or model, response.usage)
        if response.stop_reason == "refusal":
            raise AnalysisError("L'analyse de ce bilan a été refusée.", cost)
        if response.stop_reason == "max_tokens":
            raise AnalysisError("Analyse incomplète (réponse trop longue).", cost)
        text_block = next((b.text for b in response.content if b.type == "text"), None)
        try:
            result = json.loads(text_block or "")
        except json.JSONDecodeError as exc:
            raise AnalysisError("Analyse illisible.", cost) from exc
        return Analysis(
            classifications={
                int(c["operationId"]): c["category"].strip()
                for c in result.get("classifications", [])
                if c.get("category", "").strip()
            },
            analysis=[line.strip() for line in result.get("analysis", []) if line.strip()][:5],
            model=model,
            served_by=response.model or model,
            cost=cost,
        )
