"""Logique métier des messages — envoi, statuts de lecture, relance par
email (écran Messagerie). Dépend de `conversations.py` (résolution des
membres pour savoir à qui envoyer) — jamais l'inverse.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from .conversations import Conversations
from .models import Message, MessageDelivery


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Messages:
    def __init__(self, conversations: Conversations) -> None:
        self.conversations = conversations

    def envoyer(
        self,
        db: Session,
        conversation_id: int,
        expediteur_id: int,
        contenu: str,
        envoi_volontaire_email: bool = False,
    ) -> Message:
        """Crée le message + une `MessageDelivery` par destinataire résolu
        (tous les membres de la conversation, sauf l'expéditeur). Voir
        §6.9 : canal par défaut 'app', ou 'email' immédiatement si envoi
        volontaire (§5.5 : réservé Admin/Professeur — pas encore vérifié
        côté serveur, voir presence.py pour la même limitation)."""
        message = Message(conversation_id=conversation_id, expediteur_id=expediteur_id, contenu=contenu)
        db.add(message)
        db.flush()

        destinataires = [
            c
            for c in self.conversations.membres_resolus(db, conversation_id)
            if c.id != expediteur_id
        ]
        for destinataire in destinataires:
            db.add(
                MessageDelivery(
                    message_id=message.id,
                    destinataire_id=destinataire.id,
                    canal="email" if envoi_volontaire_email else "app",
                    envoi_volontaire=envoi_volontaire_email,
                )
            )
        db.commit()
        db.refresh(message)
        return message

    def messages_de_la_conversation(self, db: Session, conversation_id: int) -> list[Message]:
        return list(
            db.scalars(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at)
            )
        )

    def deliveries_du_message(self, db: Session, message_id: int) -> list[MessageDelivery]:
        return list(
            db.scalars(select(MessageDelivery).where(MessageDelivery.message_id == message_id))
        )

    def _delivery(
        self, db: Session, message_id: int, destinataire_id: int
    ) -> MessageDelivery | None:
        return db.scalar(
            select(MessageDelivery).where(
                MessageDelivery.message_id == message_id,
                MessageDelivery.destinataire_id == destinataire_id,
            )
        )

    def marquer_recu(self, db: Session, message_id: int, destinataire_id: int) -> MessageDelivery | None:
        delivery = self._delivery(db, message_id, destinataire_id)
        if delivery is None:
            return None
        if delivery.statut == "envoye":
            delivery.statut = "recu"
            delivery.recu_at = _utcnow()
            db.commit()
            db.refresh(delivery)
        return delivery

    def marquer_lu(self, db: Session, message_id: int, destinataire_id: int) -> MessageDelivery | None:
        delivery = self._delivery(db, message_id, destinataire_id)
        if delivery is None:
            return None
        delivery.statut = "lu"
        delivery.lu_at = _utcnow()
        db.commit()
        db.refresh(delivery)
        return delivery

    def envoyer_par_mail(
        self, db: Session, message_id: int, destinataire_id: int
    ) -> MessageDelivery | None:
        """Envoi volontaire par email pour CE destinataire (§5.5 : case à
        cocher, immédiat)."""
        delivery = self._delivery(db, message_id, destinataire_id)
        if delivery is None:
            return None
        delivery.canal = "email"
        delivery.envoi_volontaire = True
        db.commit()
        db.refresh(delivery)
        return delivery

    def relancer_messages_non_lus(
        self, db: Session, delai_minutes: int = 15, maintenant: dt.datetime | None = None
    ) -> list[MessageDelivery]:
        """Relance automatique (§5.5) : bascule en 'email' toute livraison
        encore 'envoye' (jamais ouverte dans l'app) après `delai_minutes`.
        Pas de scheduler dans ce backend pour l'instant — méthode pensée
        pour être appelée périodiquement (cron/tâche), ou directement
        dans les tests avec un `maintenant` fixé."""
        maintenant = maintenant or _utcnow()
        seuil = maintenant - dt.timedelta(minutes=delai_minutes)
        relancees = []
        for delivery in db.scalars(
            select(MessageDelivery).where(
                MessageDelivery.statut == "envoye", MessageDelivery.canal == "app"
            )
        ):
            envoye_at = delivery.envoye_at
            if envoye_at.tzinfo is None:
                envoye_at = envoye_at.replace(tzinfo=dt.timezone.utc)
            if envoye_at <= seuil:
                delivery.canal = "email"
                relancees.append(delivery)
        db.commit()
        for delivery in relancees:
            db.refresh(delivery)
        return relancees
