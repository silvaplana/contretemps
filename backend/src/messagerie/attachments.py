"""Photos, videos and files of the messages
(spec/modules/messagerie-instantanee.md §4.3-4.6). The content goes to the
shared storage (`storage/`), one folder per school; this class only keeps
the `msg_attachments` rows in step with it.

Videos come in blocks (§4.5), so that an upload resumes after a network cut:
the partial file waits in `<root>/_envois/`, next to a small JSON file that
says who sends it where. The ffmpeg helpers (poster, length, compression)
are the Vidéos module's.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from storage import FileTooLarge, LocalStorage, guess_mime, make_thumbnail
from videos.compression import compresser
from videos.duree import duree_secondes
from videos.poster import generer_poster

from .models import Conversation, Message, MessageAttachment

THUMBNAIL_SIZE = 320  # px, about 20 KB: what a bubble loads (§4.6)
VIDEO_MAX_BYTES = 100 * 1024 * 1024  # before compression (§4.5)
# An upload nobody finished: its partial file goes after a day.
UPLOAD_ABANDONED = dt.timedelta(days=1)
_UPLOAD_ID = re.compile(r"^[0-9a-f]{32}$")


class InvalidAttachment(ValueError):
    pass


class UploadNotFound(LookupError):
    pass


class UploadOffsetMismatch(Exception):
    """The block does not start where the file stops (a block replayed or
    lost after a cut): the client resumes from `received`."""

    def __init__(self, received: int) -> None:
        super().__init__(f"Reprendre à {received}")
        self.received = received


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
                        duration=attachment.duration,
                        compressed=attachment.compressed,
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

    # --- Videos (§4.5) ---

    def _uploads_dir(self) -> Path:
        return self.storage.root / "_envois"

    def _upload_files(self, upload_id: str) -> tuple[Path, Path]:
        if not _UPLOAD_ID.match(upload_id):
            raise UploadNotFound(upload_id)
        return self._uploads_dir() / f"{upload_id}.part", self._uploads_dir() / f"{upload_id}.json"

    def start_video_upload(
        self, conversation: Conversation, uploader_id: int, filename: str, size: int, compressed: bool
    ) -> str:
        if size > VIDEO_MAX_BYTES:
            raise FileTooLarge(VIDEO_MAX_BYTES)
        if size <= 0:
            raise InvalidAttachment("Vidéo vide")
        upload_id = uuid4().hex
        self._uploads_dir().mkdir(parents=True, exist_ok=True)
        part, meta = self._upload_files(upload_id)
        part.touch()
        meta.write_text(
            json.dumps(
                {
                    "conversation_id": conversation.id,
                    "uploader_id": uploader_id,
                    "filename": filename[:255] or "video.mp4",
                    "size": size,
                    "compressed": compressed,
                }
            )
        )
        return upload_id

    def write_video_block(
        self, db: Session, upload_id: str, uploader_id: int | None, offset: int, data: bytes
    ) -> tuple[int, MessageAttachment | None]:
        """Appends a block; the last one turns the upload into an attachment
        (returned). `uploader_id` None only in tests."""
        part, meta_path = self._upload_files(upload_id)
        if not meta_path.exists():
            raise UploadNotFound(upload_id)
        meta = json.loads(meta_path.read_text())
        if uploader_id is not None and meta["uploader_id"] != uploader_id:
            raise UploadNotFound(upload_id)
        received = part.stat().st_size
        if offset != received:
            raise UploadOffsetMismatch(received)
        if received + len(data) > meta["size"]:
            raise InvalidAttachment("La vidéo dépasse la taille annoncée")
        with open(part, "ab") as sortie:
            sortie.write(data)
        received += len(data)
        if received < meta["size"]:
            return received, None
        return received, self._finish_video(db, part, meta_path, meta)

    def _finish_video(self, db: Session, part: Path, meta_path: Path, meta: dict) -> MessageAttachment:
        conversation = db.get(Conversation, meta["conversation_id"])
        with open(part, "rb") as source:
            sha, size = self.storage.put(conversation.ecole_id, source, VIDEO_MAX_BYTES)
        part.unlink(missing_ok=True)
        meta_path.unlink(missing_ok=True)
        path = self.storage.path(conversation.ecole_id, sha)
        attachment = MessageAttachment(
            conversation_id=conversation.id,
            uploader_id=meta["uploader_id"],
            sha256=sha,
            filename=meta["filename"],
            kind="video",
            size=size,
            duration=duree_secondes(path),
            compressed=meta["compressed"],
        )
        self._make_poster(attachment, conversation.ecole_id)
        db.add(attachment)
        db.commit()
        db.refresh(attachment)
        return attachment

    def _make_poster(self, attachment: MessageAttachment, ecole_id: int) -> None:
        poster = self.storage.thumbnail_path(ecole_id, attachment.sha256)
        poster.parent.mkdir(parents=True, exist_ok=True)
        if generer_poster(self.storage.path(ecole_id, attachment.sha256), poster):
            attachment.width, attachment.height = _dimensions(poster)

    def clean_abandoned_uploads(self, now: dt.datetime | None = None) -> int:
        limit = (now or dt.datetime.now()).timestamp() - UPLOAD_ABANDONED.total_seconds()
        removed = 0
        for fichier in self._uploads_dir().glob("*"):
            if fichier.stat().st_mtime < limit:
                fichier.unlink(missing_ok=True)
                removed += 1
        return removed

    def compress_pending(self, db: Session) -> int:
        """Video worker (app/video_compression_worker.py): compresses the
        videos the phone could not compress, once. Every row sharing the
        content (forwarded copies) moves to the compressed one. A video
        ffmpeg cannot read, or that would not get smaller, stays as it is,
        never retried."""
        done = 0
        pending = db.execute(
            select(MessageAttachment.sha256, Conversation.ecole_id)
            .join(Conversation, Conversation.id == MessageAttachment.conversation_id)
            .where(MessageAttachment.kind == "video", MessageAttachment.compressed.is_(False))
            .distinct()
        ).all()
        for sha, ecole_id in pending:
            rows = list(
                db.scalars(
                    select(MessageAttachment)
                    .join(Conversation, Conversation.id == MessageAttachment.conversation_id)
                    .where(MessageAttachment.sha256 == sha, Conversation.ecole_id == ecole_id)
                )
            )
            source = self.storage.path(ecole_id, sha)
            target = source.with_name(f"{sha}-c.mp4")
            new_sha, new_size = sha, rows[0].size
            # Kept as it is when the compressed one is not smaller.
            if compresser(source, target) and target.stat().st_size < source.stat().st_size:
                with open(target, "rb") as compressed:
                    new_sha, new_size = self.storage.put(ecole_id, compressed, VIDEO_MAX_BYTES)
            target.unlink(missing_ok=True)
            for row in rows:
                row.sha256, row.size, row.compressed = new_sha, new_size, True
                if new_sha != sha:
                    row.filename = f"{Path(row.filename).stem}.mp4"  # H.264, whatever it came as
            if new_sha != sha:
                old_poster = self.storage.thumbnail_path(ecole_id, sha)
                if old_poster.exists():
                    old_poster.replace(self.storage.thumbnail_path(ecole_id, new_sha))
            db.commit()
            if new_sha != sha:
                self.storage.delete(ecole_id, sha)
                done += 1
        return done

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
