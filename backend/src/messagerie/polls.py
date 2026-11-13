"""Polls in a conversation, like WhatsApp's (Seb, 13 November 2026;
spec/modules/messagerie-instantanee.md §4.11). Same rules as the
publications poll, written again here: a module never depends on another."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import Message, MessagePoll, MessagePollOption, MessagePollVote

MAX_OPTIONS = 10


class InvalidPoll(ValueError):
    pass


def checked(question: str, options: list[str]) -> tuple[str, list[str]]:
    """The question and the answers, trimmed, without empty or repeated ones."""
    question = question.strip()
    if not question:
        raise InvalidPoll("Écrivez la question du sondage")
    labels: list[str] = []
    for option in options:
        label = option.strip()
        if label and label.lower() not in (l.lower() for l in labels):
            labels.append(label)
    if len(labels) < 2:
        raise InvalidPoll("Donnez au moins 2 réponses")
    if len(labels) > MAX_OPTIONS:
        raise InvalidPoll(f"{MAX_OPTIONS} réponses au plus")
    return question[:200], [l[:100] for l in labels]


def create(db: Session, message: Message, question: str, multiple: bool, labels: list[str]) -> None:
    db.add(MessagePoll(message_id=message.id, question=question, multiple=multiple))
    db.flush()
    for position, label in enumerate(labels):
        db.add(MessagePollOption(message_id=message.id, position=position, label=label))
    db.commit()


def of_message(db: Session, message: Message) -> dict | None:
    """The poll as everyone sees it: who voted for what, by name and id (the
    screen finds "my" vote from the id, the same event goes to everyone)."""
    if message.deleted_at is not None:
        return None
    poll = db.get(MessagePoll, message.id)
    if poll is None:
        return None
    options = list(
        db.scalars(select(MessagePollOption).where(MessagePollOption.message_id == message.id).order_by(MessagePollOption.position))
    )
    votes = list(
        db.scalars(
            select(MessagePollVote)
            .where(MessagePollVote.option_id.in_([o.id for o in options]))
            .order_by(MessagePollVote.created_at)
        )
    )
    return {
        "question": poll.question,
        "multiple": poll.multiple,
        "voters": len({v.member_id for v in votes}),
        "options": [
            {
                "id": o.id,
                "label": o.label,
                "voters": [v.name for v in votes if v.option_id == o.id],
                "voter_ids": [v.member_id for v in votes if v.option_id == o.id],
            }
            for o in options
        ],
    }


def vote(db: Session, message: Message, member_id: int, name: str, option_ids: list[int]) -> None:
    """Replaces the member's vote; an empty list withdraws it."""
    poll = db.get(MessagePoll, message.id)
    ids = set(db.scalars(select(MessagePollOption.id).where(MessagePollOption.message_id == message.id)))
    chosen = set(option_ids)
    if not chosen <= ids:
        raise InvalidPoll("Réponse introuvable")
    if len(chosen) > 1 and not poll.multiple:
        raise InvalidPoll("Une seule réponse")
    db.execute(delete(MessagePollVote).where(MessagePollVote.option_id.in_(ids), MessagePollVote.member_id == member_id))
    for option_id in chosen:
        db.add(MessagePollVote(option_id=option_id, member_id=member_id, name=name))
    db.commit()
