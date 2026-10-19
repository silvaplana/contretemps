"""Actions que les modules ouvrent à l'assistant (spec/modules/assistant-ia.md §3).

Chaque module déclare les siennes dans son propre `actions.py` ; app/main.py
les remet à l'assistant, qui n'importe aucun module. Une action devient un
outil de l'assistant ; l'appeler ne change rien : la personne voit une carte
Faire / Annuler (la même que les modifications de données), et la fonction
du module ne tourne qu'au clic.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import HTTPException
from pydantic import BaseModel
from saisons.portee import SaisonEnLectureSeule
from sqlalchemy.orm import Session

from .modifications import Ligne, Refus

logger = logging.getLogger(__name__)

PENDING_MAX = 40


@dataclass(frozen=True)
class Action:
    name: str  # nom de l'outil, ex. "create_group_chat"
    module: str  # titre de la carte, ex. "Messagerie"
    description: str  # ce que l'assistant lit pour choisir l'action
    params: type[BaseModel]  # paramètres, vérifiés avant `prepare`
    # (db, compte, org_id, params) -> Ligne : vérifie droits et données, puis
    # rend le libellé de la carte et la fonction à lancer au clic. Un refus
    # se signale par Refus, PermissionError, LookupError ou HTTPException.
    prepare: Callable[[Session, object, int, BaseModel], Ligne]
    admin_only: bool = True  # outil montré seulement aux administrateurs


class Actions:
    def __init__(self, actions: list[Action]) -> None:
        self.by_name = {a.name: a for a in actions}
        # jeton -> (org_id, person_id, ligne), en attente de « Faire ».
        self.pending: dict[str, tuple[int, int, Ligne]] = {}

    def tools(self, admin: bool) -> list[dict]:
        return [
            {"name": a.name, "description": a.description, "input_schema": a.params.model_json_schema()}
            for a in self.by_name.values()
            if admin or not a.admin_only
        ]

    def propose(self, db: Session, compte, org_id: int, person_id: int, name: str, args: dict) -> tuple[str, dict | None]:
        action = self.by_name[name]
        params = action.params.model_validate(args)  # ValueError : renvoyée telle quelle à l'assistant
        try:
            ligne = action.prepare(db, compte, org_id, params)
        except HTTPException as erreur:
            return f"Refusé : {erreur.detail}", None
        except (Refus, PermissionError, LookupError) as erreur:
            return f"Refusé : {erreur}", None
        while len(self.pending) >= PENDING_MAX:
            self.pending.pop(next(iter(self.pending)))
        jeton = uuid.uuid4().hex
        self.pending[jeton] = (org_id, person_id, ligne)
        carte = {"id": jeton[:12], "kind": "modifications", "jeton": jeton, "libelle": action.module, "lignes": [ligne.libelle]}
        return (
            f"Proposé à la personne : « {ligne.libelle} ». Elle décidera (Faire / Annuler) ; rien n'est encore fait. "
            "Tu sauras au message suivant ce qui a été fait.",
            carte,
        )

    def execute(self, db: Session, org_id: int, person_id: int, jeton: str) -> list[dict]:
        attente = self.pending.get(jeton)
        if attente is None or attente[:2] != (org_id, person_id):
            raise Refus("Cette proposition n'est plus disponible : redemandez à l'assistant.")
        self.pending.pop(jeton)
        ligne = attente[2]
        try:
            ligne.faire(db)
            db.commit()
            return [{"index": 0, "libelle": ligne.libelle, "ok": True}]
        except Exception as erreur:
            db.rollback()
            if isinstance(erreur, SaisonEnLectureSeule):
                message = "saison terminée : lecture seule"
            elif isinstance(erreur, HTTPException):
                message = str(erreur.detail)
            elif isinstance(erreur, (ValueError, PermissionError, LookupError)):
                message = str(erreur) or "refusé"
            else:
                logger.exception("Action de l'assistant en échec")
                message = "erreur inattendue"
            return [{"index": 0, "libelle": ligne.libelle, "ok": False, "erreur": message}]
