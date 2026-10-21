"""Lecture de la liste des présents d'une assemblée générale, photographiée
(spec/modules/proces-verbal-ag.md §1, étape 1), sur le modèle de
notes_frais/lecture.py : les photos partent à l'API d'Anthropic avec la
liste des membres convoqués, qui renvoie chaque nom lu et le membre qu'il
désigne. La personne vérifie les doutes avant que rien ne soit pointé.

Sans clé (`ANTHROPIC_API_KEY`), la lecture est indisponible : on coche les
présents à la main sur la feuille d'émargement.
"""

from __future__ import annotations

import base64
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field

import anthropic
from pydantic import BaseModel
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

MODEL = "claude-opus-5-5"
PRICES = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-opus-4-8": (5.0, 25.0),
}
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
PDF = "application/pdf"

INSTRUCTIONS = """Tu lis la liste des présents d'une assemblée générale d'association, signée \
à l'entrée et photographiée (une ou plusieurs pages). On te donne la liste des membres \
convoqués, chacun avec son numéro. Pour chaque personne écrite sur la feuille, dis quel \
membre elle désigne.

Règles :
- Une entrée par nom écrit, dans l'ordre de la feuille. `written` : le nom tel qu'il est \
écrit. Ignore les titres, les en-têtes de colonnes et les lignes vides.
- `person_id` : le numéro du membre, seulement si tu es sûr ; sinon null. Les noms \
peuvent être écrits dans le désordre (nom puis prénom), en majuscules, avec une initiale \
ou une faute : c'est le même membre si un seul convoqué peut correspondre.
- `candidates` : quand tu n'es pas sûr, les numéros des membres possibles (deux au plus \
souvent : homonymes, initiale partagée, écriture difficile) ; liste vide sinon.
- `doubt` : une phrase courte en français qui dit pourquoi tu n'es pas sûr (« Deux \
membres Leroy : Annie ou Claire ? », « Écriture difficile ») ; null si tu es sûr.
- Un nom qui ne correspond à aucun convoqué : person_id null, candidates vide, doubt null.
- N'ajoute jamais un membre qui n'est pas écrit sur la feuille, n'invente aucun numéro."""


class _Line(BaseModel):
    written: str
    person_id: int | None
    candidates: list[int]
    doubt: str | None


class _Reading(BaseModel):
    lines: list[_Line]


@dataclass(frozen=True)
class ReadLine:
    written: str
    person_id: int | None = None
    candidates: list[int] = field(default_factory=list)
    doubt: str | None = None


class PhotoUnreadable(Exception):
    """La lecture n'a pas eu lieu ; le message est montrable tel quel."""


def cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    prix_in, prix_out = PRICES.get(model, PRICES[MODEL])
    return round((tokens_in * prix_in + tokens_out * prix_out) / 1_000_000, 4)


class AttendanceReader:
    def __init__(
        self,
        note_cost: Callable[[Session, int, float, str], None] | None = None,
        client: anthropic.Anthropic | None = None,
    ) -> None:
        self.note_cost = note_cost
        self._client = client

    @property
    def actif(self) -> bool:
        return self._client is not None or bool(os.environ.get("ANTHROPIC_API_KEY"))

    def _get_client(self) -> anthropic.Anthropic:
        if self._client is None:
            self._client = anthropic.Anthropic()
        return self._client

    def read(self, db: Session, org_id: int, pages: list[tuple[bytes, str]], people: dict[int, str]) -> list[ReadLine]:
        """`pages` : (contenu, type) de chaque photo ; `people` : numéro ->
        nom des membres convoqués."""
        contenu = []
        for data, mime in pages:
            if mime != PDF and mime not in IMAGE_TYPES:
                raise PhotoUnreadable("Ce format de photo ne peut pas être lu : prenez une photo (JPEG ou PNG).")
            source = {"type": "base64", "media_type": mime, "data": base64.standard_b64encode(data).decode("ascii")}
            contenu.append({"type": "document" if mime == PDF else "image", "source": source})
        liste = "\n".join(f"- {pid} : {nom}" for pid, nom in people.items())
        contenu.append({"type": "text", "text": f"Membres convoqués (numéro : nom) :\n{liste}"})
        try:
            reponse = self._get_client().beta.messages.parse(
                model=MODEL,
                max_tokens=16000,
                system=INSTRUCTIONS,
                messages=[{"role": "user", "content": contenu}],
                output_config={"effort": "medium"},
                output_format=_Reading,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.RateLimitError as erreur:
            raise PhotoUnreadable("Trop de lectures en même temps : réessayez dans une minute.") from erreur
        except anthropic.APIStatusError as erreur:
            logger.exception("Lecture de la liste des présents refusée par l'API (%s)", erreur.status_code)
            raise PhotoUnreadable("La liste n'a pas pu être lue : cochez les présents à la main.") from erreur
        except anthropic.APIConnectionError as erreur:
            raise PhotoUnreadable("Le service de lecture est injoignable : réessayez plus tard.") from erreur

        if self.note_cost is not None:
            self.note_cost(db, org_id, cost_usd(reponse.model, reponse.usage.input_tokens, reponse.usage.output_tokens), reponse.model)
        lu = reponse.parsed_output
        if reponse.stop_reason == "refusal" or lu is None:
            raise PhotoUnreadable("La liste n'a pas pu être lue : reprenez la photo bien à plat, ou cochez à la main.")
        return [ReadLine(l.written, l.person_id, list(l.candidates), l.doubt) for l in lu.lines]
