"""Route de l'assistant (prototype) : une question, une réponse en flux
(Server-Sent Events). Réservée au Super User pendant l'essai (Seb, 15
octobre)."""

from __future__ import annotations

from dataclasses import replace

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
from .modifications import Refus


class Contexte(BaseModel):
    # Onglet de l'appli quand on n'est pas dans Docs (l'assistant est
    # ouvert partout, Seb 16 octobre).
    onglet: str | None = Field(default=None, max_length=40)
    space: str | None = None
    folder_id: int | None = None
    selection_id: int | None = None
    # Sélection de plusieurs éléments dans l'explorateur.
    selection_ids: list[int] = Field(default_factory=list, max_length=50)
    recents: bool = False
    # Fichier de l'appli ouvert, et le formulaire affiché (entry / result).
    app_id: int | None = None
    form: str | None = Field(default=None, pattern="^(entry|result)$")
    # Ce que la personne a fait des propositions précédentes (« Fait : … »).
    actions: list[str] = Field(default_factory=list, max_length=20)


class ChoixModifications(BaseModel):
    # Numéros (dans l'ordre de la carte) des changements cochés.
    indices: list[int] = Field(default_factory=list, max_length=100)


class Question(BaseModel):
    conversation_id: str | None = None
    texte: str = Field(min_length=1, max_length=8000)
    # Modèle choisi dans le panneau du coût (voir assistant.MODELES).
    modele: str | None = None
    # Fichiers glissés dans l'assistant : identifiants donnés par /pieces,
    # ou « doc:<id> » pour un élément glissé depuis Docs.
    pieces: list[str] = Field(default_factory=list, max_length=5)
    contexte: Contexte = Field(default_factory=Contexte)


def autorise(db: Session, compte: Compte | None) -> bool:
    """Le Super User, les administrateurs (Owners compris) et les
    professeurs (Seb, 16 octobre ; avant : le Super User seul, pendant
    l'essai). Pas les élèves. Chacun n'y fait et n'y voit que ce que ses
    écrans lui permettent déjà (donnees.py, modifications.py, Docs)."""
    if compte is None:
        return False
    return roles.is_superuser(compte) or roles.is_admin(compte) or roles.is_owner(compte) or roles.is_prof(compte)


def super_user_ou_sa_fiche(db: Session, compte: Compte) -> bool:
    """Le Super User n'est jamais bloqué par le plafond, y compris connecté
    avec sa fiche d'école (même adresse email que lui)."""
    if roles.is_superuser(compte):
        return True
    if not compte.emails:
        return False
    with toutes_saisons(db):
        superusers = db.scalars(
            select(Compte).join(RoleCompte, RoleCompte.compte_id == Compte.id).where(RoleCompte.role == roles.SUPERUSER)
        )
        return bool({e for s in superusers for e in s.emails} & set(compte.emails))


def verifier(db: Session, compte: Compte | None, org_id: int | None) -> None:
    """403 si la personne n'a pas l'assistant, ou vise une autre école que
    la sienne (seul le Super User passe d'une école à l'autre)."""
    if not autorise(db, compte):
        raise HTTPException(status_code=403, detail="L'assistant est réservé aux administrateurs et aux professeurs.")
    if not roles.is_superuser(compte) and org_id is not None and org_id != compte.ecole_id:
        raise HTTPException(status_code=403, detail="Cette école n'est pas la vôtre.")


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
            verifier(db, compte, org_id)
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
            verifier(db, compte, org_id)
            try:
                return self.client.ajouter_produit(
                    db, replace(membre, org_id=org_id), jeton, donnees.espace, donnees.dossier_parent_id
                )
            except DocError as erreur:
                raise HTTPException(status_code=erreur.status, detail=erreur.message) from erreur

        @app.post("/assistant/orgs/{org_id}/modifications/{jeton}")
        def faire_modifications(
            org_id: int,
            jeton: str,
            donnees: ChoixModifications,
            compte: Compte = Depends(rbac.compte_appelant),
            membre: Member = Depends(current_member),
            db: Session = Depends(get_db),
        ):
            """« Tout faire » sur la carte récapitulative : seulement les
            changements cochés, chacun à part (une erreur n'arrête pas les autres)."""
            verifier(db, compte, org_id)
            if self.client.modifications is None:
                raise HTTPException(status_code=403, detail="Modifications indisponibles.")
            try:
                return self.client.modifications.executer(db, compte, org_id, membre.person_id, jeton, donnees.indices)
            except Refus as erreur:
                raise HTTPException(status_code=409, detail=str(erreur)) from erreur

        @app.get("/assistant/acces")
        def acces(
            org_id: int | None = None, db: Session = Depends(get_db), compte: Compte = Depends(rbac.compte_appelant)
        ):
            """L'appli demande si elle doit ouvrir l'assistant (bulle), et le
            cumul « Chat documents » de la saison de l'école `org_id`."""
            ok = autorise(db, compte) and (
                org_id is None or roles.is_superuser(compte) or org_id == compte.ecole_id
            )
            saison = None
            # Le cumul de l'école : aux admins seulement (comme Admin > École).
            admin = ok and (roles.is_superuser(compte) or roles.is_admin(compte) or roles.is_owner(compte))
            if admin and org_id is not None and self.client.cout_saison is not None:
                saison = self.client.cout_saison(db, org_id)
            # L'éditeur en ligne (OnlyOffice) reste en essai : le Super User.
            return {"autorise": ok, "cout_saison_usd": saison, "editeur": ok and super_user_ou_sa_fiche(db, compte)}

    def _route(self):
        current_member = self.current_member

        def repondre(
            org_id: int,
            question: Question,
            compte: Compte = Depends(rbac.compte_appelant),
            membre: Member = Depends(current_member),
            db: Session = Depends(get_db),
        ):
            verifier(db, compte, org_id)
            # Plafond mensuel de l'école (Seb, 16 octobre) : jamais pour le
            # Super User.
            if self.client.plafond_atteint is not None and not super_user_ou_sa_fiche(db, compte):
                if self.client.plafond_atteint(db, org_id):
                    raise HTTPException(
                        status_code=429,
                        detail="Le budget mensuel de l'assistant de l'école est atteint. Il revient le 1er du mois.",
                    )
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
