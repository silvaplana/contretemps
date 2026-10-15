"""Route de l'assistant (prototype) : une question, une réponse en flux
(Server-Sent Events). Réservée au Super User pendant l'essai (Seb, 15
octobre)."""

from __future__ import annotations

from dataclasses import replace

from comptes import Compte, rbac, roles
from documents.ports import Member
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db import get_db

from .assistant import MODELE, Assistant


class Contexte(BaseModel):
    space: str | None = None
    folder_id: int | None = None
    selection_id: int | None = None
    recents: bool = False
    # Ce que la personne a fait des propositions précédentes (« Fait : … »).
    actions: list[str] = Field(default_factory=list, max_length=20)


class Question(BaseModel):
    conversation_id: str | None = None
    texte: str = Field(min_length=1, max_length=8000)
    # Modèle choisi dans le panneau du coût (voir assistant.MODELES).
    modele: str | None = None
    contexte: Contexte = Field(default_factory=Contexte)


class AssistantReceiver:
    def __init__(self, client: Assistant, app: FastAPI, current_member) -> None:
        self.client = client
        self.current_member = current_member
        app.post("/assistant/orgs/{org_id}/messages")(self._route())

    def _route(self):
        current_member = self.current_member

        def repondre(
            org_id: int,
            question: Question,
            compte: Compte = Depends(rbac.compte_appelant),
            membre: Member = Depends(current_member),
            db: Session = Depends(get_db),
        ):
            if not roles.is_superuser(compte):
                raise HTTPException(status_code=403, detail="L'assistant est en essai : réservé au Super User.")
            membre = replace(membre, org_id=org_id)
            conv = self.client.conversation(membre, question.conversation_id)
            return StreamingResponse(
                self.client.repondre(
                    db, membre, conv, question.texte, question.contexte.model_dump(), question.modele or MODELE
                ),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        return repondre
