"""Routes REST de la messagerie — reçoit les requêtes HTTP, délègue tout
à Conversations/Messages (voir conversations.py/messages.py), ne fait
aucun calcul métier ici à part fusionner les sorties JSON.
"""

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from db import get_db

from .conversations import Conversations
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


class MessagerieReceiver:
    def __init__(self, conversations: Conversations, messages: Messages, app: FastAPI) -> None:
        self.conversations = conversations
        self.messages = messages
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
            donnees.envoi_volontaire_email,
        )
        return self._sortie_message(db, message)

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
