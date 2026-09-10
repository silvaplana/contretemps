"""Routes REST de la messagerie — reçoit les requêtes HTTP, délègue tout
à Conversations/Messages (voir conversations.py/messages.py), ne fait
aucun calcul métier ici à part fusionner les sorties JSON.
"""

import asyncio
import json

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from db import get_db

from .conversations import Conversations
from .evenements import Evenements
from .messages import Messages
from .schemas import (
    ConversationCreation,
    ConversationModification,
    ConversationSortie,
    MembreEntree,
    MessageCreation,
    MessageSortie,
    RelanceDemande,
    StatutModification,
)

# Entre deux vrais événements, un commentaire SSE (ligne commençant par
# ":", ignorée par EventSource côté navigateur) toutes les 20s — sans ça,
# une connexion "silencieuse" trop longtemps peut être coupée par un
# proxy intermédiaire (Caddy, voir frontend/Caddyfile) qui la croit mort,
# et le navigateur ne détecterait la coupure qu'au prochain vrai essai.
DELAI_PING_SECONDES = 20


class MessagerieReceiver:
    def __init__(
        self,
        conversations: Conversations,
        messages: Messages,
        evenements: Evenements,
        app: FastAPI,
    ) -> None:
        self.conversations = conversations
        self.messages = messages
        self.evenements = evenements
        self.app = app
        self._register_routes()

    def _register_routes(self) -> None:
        self.app.get("/conversations", response_model=list[ConversationSortie])(self.lister)
        self.app.post(
            "/conversations", response_model=ConversationSortie, status_code=201
        )(self.creer)
        self.app.post("/dm", response_model=ConversationSortie, status_code=201)(
            self.creer_ou_obtenir_dm
        )
        self.app.get("/conversations/{conversation_id}", response_model=ConversationSortie)(
            self.obtenir
        )
        self.app.put(
            "/conversations/{conversation_id}", response_model=ConversationSortie
        )(self.renommer)
        self.app.delete("/conversations/{conversation_id}", status_code=204)(self.supprimer)

        self.app.post("/conversations/{conversation_id}/membres", status_code=204)(
            self.ajouter_membre
        )
        self.app.delete(
            "/conversations/{conversation_id}/membres/{membre_type}/{membre_id}",
            status_code=204,
        )(self.retirer_membre)

        self.app.get(
            "/conversations/{conversation_id}/messages", response_model=list[MessageSortie]
        )(self.lister_messages)
        self.app.post(
            "/conversations/{conversation_id}/messages",
            response_model=MessageSortie,
            status_code=201,
        )(self.envoyer_message)

        self.app.put(
            "/messages/{message_id}/deliveries/{destinataire_id}", status_code=204
        )(self.modifier_statut)
        self.app.post(
            "/messages/{message_id}/deliveries/{destinataire_id}/mail", status_code=204
        )(self.envoyer_par_mail)
        self.app.post("/messagerie/relancer", status_code=200)(self.relancer)

        self.app.post(
            "/conversations/{conversation_id}/whatsapp", response_model=ConversationSortie
        )(self.creer_groupe_whatsapp)

        # SSE (§5.5) : un flux par compte connecté, ouvert dès le login
        # (voir App.jsx) — pas de response_model (StreamingResponse, pas
        # du JSON classique).
        self.app.get("/comptes/{compte_id}/messagerie/evenements")(self.flux_evenements)

    def _sortie_conversation(self, db: Session, conversation) -> dict:
        return {
            "id": conversation.id,
            "ecole_id": conversation.ecole_id,
            "nom": conversation.nom,
            "type": conversation.type,
            "membres": self.conversations.membres_resolus(db, conversation.id),
            "blocs": self.conversations.blocs(db, conversation.id),
            "whatsapp_statut": conversation.whatsapp_statut,
            "whatsapp_groupe_id": conversation.whatsapp_groupe_id,
        }

    def lister(self, ecole_id: int, compte_id: int | None = None, db: Session = Depends(get_db)):
        if compte_id is not None:
            convs = self.conversations.lister_du_compte(db, ecole_id, compte_id)
        else:
            convs = self.conversations.lister_ecole(db, ecole_id)
        return [self._sortie_conversation(db, c) for c in convs]

    def creer(self, ecole_id: int, donnees: ConversationCreation, db: Session = Depends(get_db)):
        membres = [(m.membre_type, m.membre_id) for m in donnees.membres]
        conversation = self.conversations.create_groupe(db, ecole_id, donnees.nom, membres)
        return self._sortie_conversation(db, conversation)

    def creer_ou_obtenir_dm(
        self, ecole_id: int, compte_a_id: int, compte_b_id: int, db: Session = Depends(get_db)
    ):
        conversation = self.conversations.create_ou_obtenir_dm(
            db, ecole_id, compte_a_id, compte_b_id
        )
        return self._sortie_conversation(db, conversation)

    def obtenir(self, conversation_id: int, db: Session = Depends(get_db)):
        conversation = self.conversations.get(db, conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation introuvable")
        return self._sortie_conversation(db, conversation)

    def renommer(
        self,
        conversation_id: int,
        donnees: ConversationModification,
        db: Session = Depends(get_db),
    ):
        conversation = self.conversations.renommer(db, conversation_id, donnees.nom)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation introuvable")
        return self._sortie_conversation(db, conversation)

    def supprimer(self, conversation_id: int, db: Session = Depends(get_db)):
        if not self.conversations.delete(db, conversation_id):
            raise HTTPException(status_code=404, detail="Conversation introuvable")

    def ajouter_membre(
        self, conversation_id: int, donnees: MembreEntree, db: Session = Depends(get_db)
    ):
        self.conversations.ajouter_membre(
            db, conversation_id, donnees.membre_type, donnees.membre_id
        )

    def retirer_membre(
        self, conversation_id: int, membre_type: str, membre_id: int, db: Session = Depends(get_db)
    ):
        self.conversations.retirer_membre(db, conversation_id, membre_type, membre_id)

    def lister_messages(self, conversation_id: int, db: Session = Depends(get_db)):
        return [
            self._sortie_message(db, m)
            for m in self.messages.messages_de_la_conversation(db, conversation_id)
        ]

    def _sortie_message(self, db: Session, message) -> dict:
        return {
            "id": message.id,
            "conversation_id": message.conversation_id,
            "expediteur_id": message.expediteur_id,
            "contenu": message.contenu,
            "created_at": message.created_at,
            "deliveries": self.messages.deliveries_du_message(db, message.id),
        }

    def envoyer_message(
        self, conversation_id: int, donnees: MessageCreation, db: Session = Depends(get_db)
    ):
        message = self.messages.envoyer(
            db,
            conversation_id,
            donnees.expediteur_id,
            donnees.contenu,
            donnees.canal,
        )
        sortie = self._sortie_message(db, message)
        self._publier_message(db, conversation_id, sortie)
        return sortie

    def _publier_message(self, db: Session, conversation_id: int, sortie: dict) -> None:
        """Pousse le nouveau message sur le flux SSE de chaque membre de
        la conversation (voir evenements.py) — y compris l'expéditeur
        (pour qu'un autre onglet/appareil du même compte se resynchronise
        aussi), pas seulement les autres destinataires."""
        # `mode="json"` : sérialise created_at (datetime) en texte —
        # sinon json.dumps plus bas plante (TypeError: not serializable).
        evenement_message = MessageSortie.model_validate(sortie).model_dump(mode="json")
        for membre in self.conversations.membres_resolus(db, conversation_id):
            self.evenements.publier(
                membre.id,
                {"type": "message", "conversation_id": conversation_id, "message": evenement_message},
            )

    def modifier_statut(
        self,
        message_id: int,
        destinataire_id: int,
        donnees: StatutModification,
        db: Session = Depends(get_db),
    ):
        if donnees.statut == "lu":
            delivery = self.messages.marquer_lu(db, message_id, destinataire_id)
        else:
            delivery = self.messages.marquer_recu(db, message_id, destinataire_id)
        if delivery is None:
            raise HTTPException(status_code=404, detail="Livraison introuvable")

    def envoyer_par_mail(self, message_id: int, destinataire_id: int, db: Session = Depends(get_db)):
        delivery = self.messages.envoyer_par_mail(db, message_id, destinataire_id)
        if delivery is None:
            raise HTTPException(status_code=404, detail="Livraison introuvable")

    def relancer(self, donnees: RelanceDemande, db: Session = Depends(get_db)):
        relancees = self.messages.relancer_messages_non_lus(db, donnees.delai_minutes)
        return {"relancees": len(relancees)}

    def creer_groupe_whatsapp(self, conversation_id: int, db: Session = Depends(get_db)):
        conversation = self.conversations.creer_groupe_whatsapp(db, conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation introuvable")
        return self._sortie_conversation(db, conversation)

    def flux_evenements(self, compte_id: int) -> StreamingResponse:
        return StreamingResponse(
            self._generateur_evenements(compte_id), media_type="text/event-stream"
        )

    async def _generateur_evenements(self, compte_id: int):
        queue = self.evenements.abonner(compte_id)
        try:
            # Un premier commentaire tout de suite : certains proxies/
            # navigateurs attendent le premier octet avant de considérer
            # la connexion "ouverte" (voir EventSource : onopen).
            yield ": connecte\n\n"
            while True:
                try:
                    evenement = await asyncio.wait_for(queue.get(), timeout=DELAI_PING_SECONDES)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue
                yield f"data: {json.dumps(evenement)}\n\n"
        finally:
            # Atteint quand le client ferme la connexion (l'ASGI annule
            # ce générateur, voir Starlette : StreamingResponse) — sans
            # ce désabonnement, `Evenements` garderait une queue morte
            # pour toujours (fuite mémoire lente à chaque reconnexion).
            self.evenements.desabonner(compte_id, queue)
