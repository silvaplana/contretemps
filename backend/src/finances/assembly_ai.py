"""Rédaction du texte des diapos d'une assemblée générale par un modèle de
langage (API Claude, mêmes modèles et même calcul du coût que le bilan :
voir ai.py), repris de Sambo Admin (generalassemblies/ai.py).

Le modèle reçoit le plan du PowerPoint modèle (zones de texte de chaque
diapo), les chiffres du bilan de la saison et les inscrits par saison. Il
réécrit les parties du trésorier (rapport d'activité, bilan, recettes,
dépenses, résultat, budget prévisionnel), met les années à jour et marque
« À compléter » ce qu'il ne sait pas. L'appli place ensuite ce texte dans le
PowerPoint (voir slides.fill) et vérifie les montants.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import anthropic

from .ai import DEFAULT_MODEL, MODELS, AnalysisError, cost_usd
from .slides import TO_COMPLETE

INSTRUCTIONS = f"""Tu es le trésorier bénévole d'une association.
Tu prépares la base du PowerPoint de l'assemblée générale (AG) d'une saison.

On te donne :
- "modele" : le plan du PowerPoint de l'AG précédente, diapo par diapo. Chaque diapo a des zones de texte (identifiant "zone", rôle "titre" ou "texte") et leurs paragraphes avec leur niveau de puce (0 = puce principale, 1 = sous-puce...). "\\n" est un retour à la ligne dans un paragraphe.
- "bilan" : le bilan de la saison, calculé par l'application au centime à partir des relevés de banque, avec son analyse et la saison précédente pour comparer.
- "inscrits" : le nombre d'inscrits par saison.

Ta mission : réécrire pour la saison demandée les zones qui doivent changer, en gardant le style du modèle (phrases courtes, mêmes niveaux de puces, à peu près le même nombre de lignes pour que le texte tienne sur la diapo).
1. Parties du trésorier, à remplir avec les données : rapport d'activité (inscrits de la saison et des saisons précédentes), bilan (période des comptes), résumé (résultat, soldes de début et de fin), recettes (vue globale et analyse par rapport à la saison précédente), dépenses (vue globale et analyse), résultat global, budget prévisionnel de la saison suivante.
2. Années : remplace partout les saisons et années de l'AG précédente par celles de la saison demandée (titres compris, par exemple « Projets 2026-2027 » devient « Projets 2027-2028 » pour la saison 2026-2027).
3. Autres diapos (accueil, bureau, projets, objectifs, renouvellement, questions, clôture) : ne les change pas, sauf les années, et sauf un contenu qui ne vaut que pour l'AG précédente (noms, démissions, dates, événements passés) : remplace-le par « {TO_COMPLETE} ».

Règles :
- Les montants viennent uniquement des données fournies, arrondis à l'euro (ex : « 15 718 € »). N'additionne et ne soustrais aucun montant toi-même : cite ceux qui sont fournis. N'invente aucun chiffre.
- Ce que les données ne disent pas (date de l'AG, nom du trésorier, prix de la cotisation, subventions non visibles en banque, budget prévisionnel chiffré, explications des variations...) : écris exactement « {TO_COMPLETE} » à la place de l'information.
- Une recette ou une dépense exceptionnelle (qui ne se reproduira pas) doit être signalée comme telle.
- Si la saison n'est pas terminée (date d'arrêt avant la fin de saison), dis que les comptes sont arrêtés à cette date.
- Ne renvoie que les zones que tu modifies, avec tous leurs paragraphes (le texte complet de la zone). Ne modifie pas les diapos masquées.
- "resume" : 3 lignes au plus pour le trésorier : ce que tu as rempli et ce qui reste à compléter.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "zones": {
            "type": "array",
            "description": "Zones de texte modifiées, avec leur texte complet.",
            "items": {
                "type": "object",
                "properties": {
                    "diapo": {"type": "integer"},
                    "zone": {"type": "integer"},
                    "paragraphes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"niveau": {"type": "integer"}, "texte": {"type": "string"}},
                            "required": ["niveau", "texte"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["diapo", "zone", "paragraphes"],
                "additionalProperties": False,
            },
        },
        "resume": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["zones", "resume"],
    "additionalProperties": False,
}


@dataclass
class Draft:
    zones: list[dict]
    summary: list[str]
    model: str  # clé de MODELS
    served_by: str
    cost: float  # dollars


class Writer:
    def __init__(self, client: anthropic.Anthropic | None = None) -> None:
        self._client = client

    def _anthropic(self) -> anthropic.Anthropic:
        if self._client is None:
            self._client = anthropic.Anthropic()
        return self._client

    def write(self, model: str, data: dict, prompt: str) -> Draft:
        """data : plan du modèle et chiffres (voir GeneralAssemblies._ai_data) ;
        prompt : consignes saisies dans l'écran (peut être vide)."""
        if model not in MODELS:
            raise AnalysisError(f"Modèle inconnu : {model}")
        text = "Données (JSON) :\n" + json.dumps(data, ensure_ascii=False, indent=1)
        if prompt.strip():
            text += "\n\nConsignes du trésorier pour cette AG :\n" + prompt.strip()
        params = {
            "model": model,
            "max_tokens": 32000,
            "system": INSTRUCTIONS,
            "messages": [{"role": "user", "content": text}],
            "output_config": {"format": {"type": "json_schema", "schema": SCHEMA}},
        }
        if model != "claude-haiku-5-5":
            # Comme le bilan : si le modèle décline, l'API relance la demande
            # sur le modèle de secours recommandé.
            params["betas"] = ["server-side-fallback-2026-07-01"]
            params["fallbacks"] = "default"
        try:
            with self._anthropic().beta.messages.stream(**params) as stream:
                response = stream.get_final_message()
        except Exception as exc:  # noqa: BLE001 - toute erreur de l'appel en message clair
            raise AnalysisError(f"La préparation du PowerPoint a échoué : {exc}") from exc

        cost = cost_usd(response.model or model, response.usage)
        if response.stop_reason == "refusal":
            raise AnalysisError("La préparation de cette AG a été refusée.", cost)
        if response.stop_reason == "max_tokens":
            raise AnalysisError("Préparation incomplète (réponse trop longue).", cost)
        text_block = next((b.text for b in response.content if b.type == "text"), None)
        try:
            result = json.loads(text_block or "")
        except json.JSONDecodeError as exc:
            raise AnalysisError("Réponse illisible.", cost) from exc
        return Draft(
            zones=[z for z in result.get("zones", []) if isinstance(z, dict)],
            summary=[line.strip() for line in result.get("resume", []) if line.strip()][:3],
            model=model,
            served_by=response.model or model,
            cost=cost,
        )


__all__ = ["DEFAULT_MODEL", "MODELS", "AnalysisError", "Draft", "Writer"]
