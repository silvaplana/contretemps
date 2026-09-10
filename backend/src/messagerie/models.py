"""Tables de la messagerie (voir spec/SPEC.md §6.9). Un seul concept
"conversation" pour Admin > Conversations et l'écran Messagerie — les
droits diffèrent selon l'écran, pas les données (voir backend-architecture
côté mémoire projet).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecole_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id"), nullable=False, index=True)
    nom: Mapped[str | None] = mapped_column(String(150), nullable=True)
    # 'individuelle' | 'groupe' — texte, pas Enum (même choix que
    # comptes.role, voir backend/README.md).
    type: Mapped[str] = mapped_column(String(20), nullable=False)

    # Groupe WhatsApp miroir (voir spec/SPEC.md §6.9 et conversations.py :
    # creer_groupe_whatsapp) — le "tuyau" pour un futur envoi réel via
    # Baileys, pas encore branché : 'aucun' (par défaut) | 'cree'. L'id du
    # groupe WhatsApp (ex. "1234567890-1234567890@g.us") reste NULL tant
    # qu'aucune vraie création n'a eu lieu.
    whatsapp_statut: Mapped[str] = mapped_column(String(20), nullable=False, default="aucun")
    whatsapp_groupe_id: Mapped[str | None] = mapped_column(String(100), nullable=True)


class ConversationMembre(Base):
    """Champ polymorphe (membre_type + membre_id) — PAS une vraie FK SQL
    (voir §6.9 : "l'intégrité référentielle doit être vérifiée côté
    application"). 'cours' se résout dynamiquement en tous ses élèves et
    professeur(s), pas de liste figée (voir conversations.py)."""

    __tablename__ = "conversation_membres"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id"), nullable=False, index=True
    )
    # 'compte' | 'cours'
    membre_type: Mapped[str] = mapped_column(String(20), nullable=False)
    membre_id: Mapped[int] = mapped_column(Integer, nullable=False)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id"), nullable=False, index=True
    )
    expediteur_id: Mapped[int] = mapped_column(ForeignKey("comptes.id"), nullable=False)
    contenu: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class MessageDelivery(Base):
    """UNE LIGNE PAR (message, destinataire) : coches envoyé/reçu/vu *par
    personne* (voir §6.9), essentiel dans une conversation à plusieurs
    membres où chacun peut être à un statut différent."""

    __tablename__ = "message_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"), nullable=False, index=True)
    destinataire_id: Mapped[int] = mapped_column(ForeignKey("comptes.id"), nullable=False, index=True)
    # 'app' | 'email' | 'whatsapp' — canal = 'email' -> icône mail à côté
    # du message. 'whatsapp' est un marqueur d'INTENTION seulement, pas un
    # vrai envoi (voir messages.py: envoyer et spec/SPEC.md §6.9/§8) —
    # aucun message ne part réellement sur WhatsApp pour l'instant.
    canal: Mapped[str] = mapped_column(String(10), nullable=False, default="app")
    # 'envoye' | 'recu' | 'lu'
    statut: Mapped[str] = mapped_column(String(10), nullable=False, default="envoye")
    envoi_volontaire: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    envoye_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    recu_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    lu_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
