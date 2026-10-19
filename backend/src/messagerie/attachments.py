"""Photos and files of the messages (spec/modules/messagerie-instantanee.md
§4.3-4.4, §4.6). The content goes to the shared storage (`storage/`), one
folder per school; this class only keeps the `msg_attachments` rows in step
with it.
"""

from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from storage import LocalStorage, guess_mime, make_thumbnail

from .models import Conversation, Message, MessageAttachment

THUMBNAIL_SIZE = 320  # px, about 20 KB: what a bubble loads (§4.6)


class InvalidAttachment(ValueError):
    pass


class Attachments:
    def __init__(self, storage: LocalStorage) -> None:
        self.storage = storage

    def upload(
        self, db: Session, conversation: Conversation, uploader_id: int, filename: str, source: BinaryIO
    ) -> MessageAttachment:
        """Stores the content (raises FileTooLarge over the limit). An image
        the server can read becomes a photo, with its thumbnail; anything
        else is a file, untouched."""
        sha, size = self.storage.put(conversation.ecole_id, source)
        attachment = MessageAttachment(
            conversation_id=conversation.id,
            uploader_id=uploader_id,
            sha256=sha,
            filename=filename[:255] or "fichier",
            kind="file",
            size=size,
        )
        if guess_mime(filename).startswith("image/"):
            path = self.storage.path(conversation.ecole_id, sha)
            if make_thumbnail(path, self.storage.thumbnail_path(conversation.ecole_id, sha), THUMBNAIL_SIZE):
                attachment.kind = "photo"
                attachment.width, attachment.height = _dimensions(path)
        db.add(attachment)
        db.commit()
        db.refresh(attachment)
        return attachment

    def get(self, db: Session, attachment_id: int) -> MessageAttachment | None:
        return db.get(MessageAttachment, attachment_id)

    def of_message(self, db: Session, message_id: int) -> list[MessageAttachment]:
        return list(
            db.scalars(
                select(MessageAttachment)
                .where(MessageAttachment.message_id == message_id)
                .order_by(MessageAttachment.id)
            )
        )

    def check(
        self, db: Session, ids: list[int], conversation: Conversation, sender_id: int, can_read
    ) -> list[MessageAttachment]:
        """Before sending: each id is either a photo or file the sender has
        just uploaded to this conversation, or one of an existing message
        they can read (Transférer, §4.2), in the same school. `can_read(
        conversation_id)` says whether the sender belongs to it."""
        found = []
        for attachment_id in ids:
            attachment = self.get(db, attachment_id)
            if attachment is None:
                raise InvalidAttachment("Pièce jointe introuvable")
            if attachment.message_id is None:
                ok = attachment.uploader_id == sender_id and attachment.conversation_id == conversation.id
            else:
                source = db.get(Conversation, attachment.conversation_id)
                ok = source.ecole_id == conversation.ecole_id and can_read(source.id)
            if not ok:
                raise InvalidAttachment("Pièce jointe introuvable")
            found.append(attachment)
        return found

    def attach(self, db: Session, message: Message, attachments: list[MessageAttachment]) -> None:
        """A fresh upload is tied to the message; a forwarded one is copied
        (a new row, same content on disk)."""
        for attachment in attachments:
            if attachment.message_id is None:
                attachment.message_id = message.id
            else:
                db.add(
                    MessageAttachment(
                        message_id=message.id,
                        conversation_id=message.conversation_id,
                        uploader_id=message.expediteur_id,
                        sha256=attachment.sha256,
                        filename=attachment.filename,
                        kind=attachment.kind,
                        size=attachment.size,
                        width=attachment.width,
                        height=attachment.height,
                    )
                )
        db.commit()

    def remove_from_message(self, db: Session, message: Message, ecole_id: int) -> None:
        """Deleted message: its rows go, and a content nothing else uses
        any more leaves the disk (§4.2)."""
        attachments = self.of_message(db, message.id)
        for attachment in attachments:
            db.delete(attachment)
        db.flush()
        for sha in {a.sha256 for a in attachments}:
            still_used = db.scalar(
                select(func.count())
                .select_from(MessageAttachment)
                .join(Conversation, Conversation.id == MessageAttachment.conversation_id)
                .where(MessageAttachment.sha256 == sha, Conversation.ecole_id == ecole_id)
            )
            if not still_used:
                self.storage.delete(ecole_id, sha)
        db.commit()

    def content_path(self, attachment: MessageAttachment, ecole_id: int) -> Path:
        return self.storage.path(ecole_id, attachment.sha256)

    def thumbnail_path(self, attachment: MessageAttachment, ecole_id: int) -> Path:
        return self.storage.thumbnail_path(ecole_id, attachment.sha256)


def _dimensions(path: Path) -> tuple[int | None, int | None]:
    try:
        from PIL import Image, ImageOps

        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image)
            return image.size
    except Exception:
        return None, None
