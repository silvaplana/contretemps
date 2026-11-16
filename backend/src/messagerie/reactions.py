"""Emoji reactions on a message, like WhatsApp (Seb, 16 November 2026;
spec/modules/messagerie-instantanee.md §4.12): one per person, another one
replaces it, none withdraws it."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Message, MessageReaction


class InvalidReaction(ValueError):
    pass


def of_message(db: Session, message: Message) -> list[dict]:
    """Who reacted with what, oldest first; nothing on a deleted message."""
    if message.deleted_at is not None:
        return []
    reactions = db.scalars(
        select(MessageReaction).where(MessageReaction.message_id == message.id).order_by(MessageReaction.created_at)
    )
    return [{"emoji": r.emoji, "member_id": r.member_id, "name": r.name} for r in reactions]


def react(db: Session, message: Message, member_id: int, name: str, emoji: str | None) -> None:
    """Replaces the member's reaction; None withdraws it."""
    emoji = (emoji or "").strip()
    if len(emoji) > 16:
        raise InvalidReaction("Une seule émoji")
    reaction = db.get(MessageReaction, (message.id, member_id))
    if reaction is not None:
        db.delete(reaction)
        db.flush()
    if emoji:
        db.add(MessageReaction(message_id=message.id, member_id=member_id, name=name[:100], emoji=emoji))
    db.commit()
