"""Route de l'assistant (prototype) : une question, une réponse en flux
(Server-Sent Events). Réservée au Super User pendant l'essai (Seb, 15
octobre)."""

from __future__ import annotations

from dataclasses import replace

from acces import normaliser_email
from comptes import Compte, rbac, roles
from comptes.models import RoleCompte
from saisons.portee import toutes_saisons
from sqlalchemy import select
from documents.ports import Member
from documents.service import DocError
from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db import get_db

from .assistant import MODELE, Assistant


class Contexte(BaseModel):
    space: str | None = None
    folder_id: int | None = None
    selection_id: int | None = None
    # Sélection de plusieurs éléments dans l'explorateur.
    selection_ids: list[int] = Field(default_factory=list, max_length=50)
    recents: bool = False
    # Ce que la personne a fait des propositions précédentes (« Fait : … »).
    actions: list[str] = Field(default_factory=list, max_length=20)


class Question(BaseModel):
    conversation_id: str | None = None
    texte: str = Field(min_length=1, max_length=8000)
    # Modèle choisi dans le panneau du coût (voir assistant.MODELES).
    modele: str | None = None
    # Fichiers glissés dans l'assistant (identifiants donnés par /pieces).
    pieces: list[str] = Field(default_factory=list, max_length=5)
    contexte: Contexte = Field(default_factory=Contexte)


def autorise(db: Session, compte: Compte) -> bool:
    """Pendant l'essai, « toi seul » (Seb, 15 octobre) : le Super User, ou
    une fiche d'école qui a la même adresse email que lui (Seb se connecte
    le plus souvent avec sa fiche d'admin de l'école)."""
    if roles.is_superuser(compte):
        return True
    if not compte.email:
        return False
    with toutes_saisons(db):
        emails = db.scalars(
            select(Compte.email).join(RoleCompte, RoleCompte.compte_id == Compte.id).where(RoleCompte.role == roles.SUPERUSER)
        )
        return normaliser_email(compte.email) in {normaliser_email(e) for e in emails if e}


class AjoutProduit(BaseModel):
    espace: str
    dossier_parent_id: int | None = None


class AssistantReceiver:
    def __init__(self, client: Assistant, app: FastAPI, current_member) -> None:
        self.client = client
        self.current_member = current_member
        app.post("/assistant/orgs/{org_id}/messages")(self._route())

        @app.post("/assistant/orgs/{org_id}/pieces")
        async def deposer_piece(
            org_id: int,
            fichier: UploadFile,
            compte: Compte = Depends(rbac.compte_appelant),
            membre: Member = Depends(current_member),
            db: Session = Depends(get_db),
        ):
            """Fichier glissé dans l'assistant, joint à la question suivante."""
            if not autorise(db, compte):
                raise HTTPException(status_code=403, detail="L'assistant est en essai : réservé au Super User.")
            try:
                return self.client.deposer_piece(replace(membre, org_id=org_id), fichier.filename, await fichier.read())
            except DocError as erreur:
                raise HTTPException(status_code=erreur.status, detail=erreur.message) from erreur

        @app.post("/assistant/orgs/{org_id}/produits/{jeton}")
        def ajouter_produit(
            org_id: int,
            jeton: str,
            donnees: AjoutProduit,
            compte: Compte = Depends(rbac.compte_appelant),
            membre: Member = Depends(current_member),
            db: Session = Depends(get_db),
        ):
            """« Faire » sur un fichier fabriqué par l'ordinateur de l'assistant."""
            if not autorise(db, compte):
                raise HTTPException(status_code=403, detail="L'assistant est en essai : réservé au Super User.")
            try:
                return self.client.ajouter_produit(
                    db, replace(membre, org_id=org_id), jeton, donnees.espace, donnees.dossier_parent_id
                )
            except DocError as erreur:
                raise HTTPException(status_code=erreur.status, detail=erreur.message) from erreur

        @app.get("/assistant/acces")
        def acces(
            org_id: int | None = None, db: Session = Depends(get_db), compte: Compte = Depends(rbac.compte_appelant)
        ):
            """L'appli demande si elle doit ouvrir l'assistant (bulle), et le
            cumul « Chat documents » de la saison de l'école `org_id`."""
            ok = autorise(db, compte)
            saison = None
            if ok and org_id is not None and self.client.cout_saison is not None:
                saison = self.client.cout_saison(db, org_id)
            return {"autorise": ok, "cout_saison_usd": saison}

    def _route(self):
        current_member = self.current_member

        def repondre(
            org_id: int,
            question: Question,
            compte: Compte = Depends(rbac.compte_appelant),
            membre: Member = Depends(current_member),
            db: Session = Depends(get_db),
        ):
            if not autorise(db, compte):
                raise HTTPException(status_code=403, detail="L'assistant est en essai : réservé au Super User.")
            membre = replace(membre, org_id=org_id)
            conv = self.client.conversation(membre, question.conversation_id)
            return StreamingResponse(
                self.client.repondre(
                    db, membre, conv, question.texte, question.contexte.model_dump(), question.modele or MODELE, compte,
                    question.pieces,
                ),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        return repondre
