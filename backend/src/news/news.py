"""What the news module does (spec/modules/actualites.md), without HTTP.

Every query filters by organization. The push notification leaves 10 s
after publishing, so that « Annuler » can still stop it (§5)."""

from __future__ import annotations

import io
import logging
import threading
from datetime import date, datetime, timezone

from typing import BinaryIO

from comptes import Compte, roles
from documents.models import DocNode
from ecoles.models import Ecole
from groups import rights
from saisons.portee import toutes_saisons
from saisons.saisons import saison_courante_id
from sqlalchemy import select
from sqlalchemy.orm import Session
from storage import FileTooLarge, LocalStorage, make_thumbnail
from videos import Videos
from videos.models import Video

from . import links
from .models import BRIEF, IMPORTANT, NewsItem, NewsMedia, NewsSeen, NewsSettings
from .storage import DISPLAY_SIZE

logger = logging.getLogger(__name__)

UNDO_SECONDS = 10
MAX_MEDIA = 10  # like an Instagram carousel
PUBLISH = "news.publish"
# While the module is being tried out (Seb, 8 November): only the members of
# the 🔒 group « Voir les actualités », and those who publish, see the news.
READ = "news.read"
PREVIEW_CHARS = 100


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def can_publish(compte: Compte | None) -> bool:
    # `None`: rights switched off (tests, see tests/conftest.py).
    return compte is None or roles.has_right(compte, PUBLISH)


def can_read(compte: Compte | None) -> bool:
    return can_publish(compte) or roles.has_right(compte, READ)


def on_top(item: NewsItem, today: date) -> bool:
    return item.level == IMPORTANT and item.on_top_until is not None and item.on_top_until >= today


class InvalidMedia(ValueError):
    """A photo, video or document that cannot go in this item."""


class News:
    def __init__(self, notifications, storage: LocalStorage, videos: Videos, session_factory=None,
                 delay_seconds: float | None = UNDO_SECONDS) -> None:
        self.notifications = notifications
        self.storage = storage
        self.videos = videos
        # A video deleted elsewhere (Usage panel) leaves its news item.
        videos.quand_supprimee(self._video_deleted)
        videos.rubrique("Actualités", lambda db: set(db.scalars(select(NewsMedia.video_id).where(NewsMedia.video_id.is_not(None)))))
        # Where the delayed notification opens its own session; None (tests):
        # nothing is scheduled, `send_notification` is called by hand.
        self.session_factory = session_factory
        self.delay_seconds = delay_seconds

    # --- Reading ---

    def get(self, db: Session, org_id: int, item_id: int) -> NewsItem | None:
        item = db.get(NewsItem, item_id)
        return item if item is not None and item.org_id == org_id else None

    def published(self, db: Session, org_id: int, today: date | None = None) -> list[NewsItem]:
        """The feed: Important items still on top, then everything else,
        newest first (§3.2)."""
        today = today or date.today()
        items = list(db.scalars(
            select(NewsItem)
            .where(NewsItem.org_id == org_id, NewsItem.published_at.is_not(None))
            .order_by(NewsItem.published_at.desc(), NewsItem.id.desc())
        ))
        return [i for i in items if on_top(i, today)] + [i for i in items if not on_top(i, today)]

    def workshop(self, db: Session, org_id: int) -> list[NewsItem]:
        """Everything, drafts included, newest first (§4.1)."""
        return list(db.scalars(
            select(NewsItem).where(NewsItem.org_id == org_id).order_by(NewsItem.updated_at.desc(), NewsItem.id.desc())
        ))

    def last_seen(self, db: Session, compte_id: int) -> datetime | None:
        seen = db.get(NewsSeen, compte_id)
        return seen.seen_at if seen else None

    def mark_seen(self, db: Session, compte_id: int) -> None:
        seen = db.get(NewsSeen, compte_id)
        if seen is None:
            db.add(NewsSeen(compte_id=compte_id, seen_at=_now()))
        else:
            seen.seen_at = _now()
        db.commit()

    def open_on_news(self, db: Session, org_id: int) -> bool:
        settings = db.get(NewsSettings, org_id)
        return True if settings is None else settings.open_on_news

    def set_open_on_news(self, db: Session, org_id: int, value: bool) -> None:
        self._settings(db, org_id).open_on_news = value
        db.commit()

    def media_first(self, db: Session, org_id: int) -> bool:
        settings = db.get(NewsSettings, org_id)
        return False if settings is None else settings.media_first

    def set_media_first(self, db: Session, org_id: int, value: bool) -> None:
        self._settings(db, org_id).media_first = value
        db.commit()

    def _settings(self, db: Session, org_id: int) -> NewsSettings:
        settings = db.get(NewsSettings, org_id)
        if settings is None:
            settings = NewsSettings(org_id=org_id, open_on_news=True, media_first=False)
            db.add(settings)
        return settings

    # --- Who sees the news while in test (§2 bis) ---

    def members(self, db: Session, org_id: int) -> list[Compte]:
        """The members of the current season, by first name."""
        season = saison_courante_id(db, org_id)
        with toutes_saisons(db):
            return list(db.scalars(
                select(Compte).where(Compte.ecole_id == org_id, Compte.saison_id == season)
                .order_by(Compte.prenom, Compte.nom)
            ))

    def set_reader(self, db: Session, compte: Compte, reads: bool) -> None:
        (rights.add if reads else rights.remove)(db, compte, READ)
        db.commit()

    # --- Media (§3.3) ---

    def store_photo(self, org_id: int, source: BinaryIO) -> str:
        """Keeps a photo sent from the editor; returns its sha256, which
        the item then names. Raises InvalidMedia if it is not an image."""
        sha, _ = self.storage.put(org_id, source)
        if not make_thumbnail(self.storage.path(org_id, sha), self.storage.thumbnail_path(org_id, sha), DISPLAY_SIZE):
            self.storage.delete(org_id, sha)
            raise InvalidMedia("Ce fichier n'est pas une photo")
        return sha

    def read_link(self, org_id: int, url: str) -> tuple[str, str | None]:
        """A link added to the carousel: its title and the sha of its
        picture, kept like a photo (None if the site has none). Raises
        LinkError."""
        preview = links.read(url)
        photo = None
        if preview.image:
            try:
                photo = self.store_photo(org_id, io.BytesIO(preview.image))
            except (InvalidMedia, FileTooLarge):
                photo = None
        return preview.title, photo

    def thumbnail(self, org_id: int, sha: str):
        return self.storage.thumbnail_path(org_id, sha)

    def photo_path(self, item: NewsItem, sha: str):
        """The JPEG shown in the news (at most 1600 px), if this item has it."""
        if not any(m.photo_sha == sha for m in item.media):
            return None
        return self.storage.thumbnail_path(item.org_id, sha)

    def media(self, db: Session, item: NewsItem) -> list[tuple[NewsMedia, Video | None]]:
        """Each media of the item, in order, with its video. A video
        belongs to a season; the item outlives it."""
        with toutes_saisons(db):
            videos = {m.video_id: db.get(Video, m.video_id) for m in item.media if m.video_id}
        return [(m, videos.get(m.video_id)) for m in item.media]

    def document(self, db: Session, item: NewsItem) -> DocNode | None:
        if item.document_id is None:
            return None
        node = db.get(DocNode, item.document_id)
        return node if node is not None and node.deleted_at is None else None

    def _check_media(self, db: Session, org_id: int, media: list[dict], document_id) -> None:
        if len(media) > MAX_MEDIA:
            raise InvalidMedia(f"{MAX_MEDIA} photos ou vidéos au plus")
        for entry in media:
            photo, video_id, link = entry.get("photo"), entry.get("video_id"), entry.get("link")
            if link and (video_id or not link.startswith(("http://", "https://"))):
                raise InvalidMedia("Lien invalide")
            if not link and bool(photo) == bool(video_id):
                raise InvalidMedia("Chaque élément est une photo, une vidéo ou un lien")
            if photo and not self.storage.thumbnail_path(org_id, photo).exists():
                raise InvalidMedia("Photo introuvable")
            if video_id:
                with toutes_saisons(db):
                    video = db.get(Video, video_id)
                if video is None or video.ecole_id != org_id:
                    raise InvalidMedia("Vidéo introuvable")
        if document_id:
            node = db.get(DocNode, document_id)
            if node is None or node.org_id != org_id or node.kind == "folder" or node.deleted_at is not None:
                raise InvalidMedia("Document introuvable")

    def _forget(self, db: Session, org_id: int, photos: set, videos: set) -> None:
        """Deletes the photos no item names any more, and the videos given."""
        for sha in photos:
            named = db.scalar(
                select(NewsMedia.id).join(NewsItem, NewsItem.id == NewsMedia.item_id)
                .where(NewsItem.org_id == org_id, NewsMedia.photo_sha == sha)
            )
            if named is None:
                self.storage.delete(org_id, sha)
        if videos:
            with toutes_saisons(db):
                for video_id in videos:
                    self.videos.delete(db, video_id)

    def _video_deleted(self, db: Session, video_id: int) -> None:
        for media in db.scalars(select(NewsMedia).where(NewsMedia.video_id == video_id)):
            db.delete(media)

    # --- Writing ---

    def save(self, db: Session, org_id: int, author: Compte | None, item: NewsItem | None, *,
             level: str, body: str, on_top_until: date | None, notify: bool, publish: bool,
             media: list[dict] | None = None, document_id: int | None = None) -> NewsItem:
        """Creates (`item=None`) or changes an item. `media`: its photos and
        videos in order, each {"photo": sha}, {"video_id": id} or
        {"link": url, "title": …, "photo": sha of its picture}. `publish`
        puts it in the feed, or back in the drafts. A brief has no media.
        Raises InvalidMedia."""
        media = [] if level == BRIEF or media is None else media
        if level == BRIEF:
            document_id = None
        self._check_media(db, org_id, media, document_id)
        old_photos = {m.photo_sha for m in item.media if m.photo_sha} if item else set()
        old_videos = {m.video_id for m in item.media if m.video_id} if item else set()
        if item is None:
            item = NewsItem(org_id=org_id, author_id=author.id if author else None,
                            author_name=author.prenom if author else "")
            db.add(item)
        item.level = level
        item.body = body.strip()
        item.on_top_until = on_top_until if level == IMPORTANT else None
        item.notify = notify
        item.media = [
            NewsMedia(position=i, photo_sha=m.get("photo"), video_id=m.get("video_id"),
                      link_url=m.get("link"), link_title=(m.get("title") or "")[:300] if m.get("link") else None)
            for i, m in enumerate(media)
        ]
        item.document_id = document_id
        newly_published = publish and item.published_at is None
        if publish and item.published_at is None:
            item.published_at = _now()
        if not publish:
            item.published_at = None
        db.commit()
        self._forget(db, org_id, old_photos - {m.get("photo") for m in media},
                     old_videos - {m.get("video_id") for m in media})
        db.refresh(item)
        if newly_published and notify and item.notified_at is None:
            self._schedule(item.id)
        return item

    def unpublish(self, db: Session, item: NewsItem) -> NewsItem:
        """« Annuler » right after Publier: back to the drafts, and the
        notification, not sent yet, will not leave."""
        item.published_at = None
        db.commit()
        db.refresh(item)
        return item

    def delete(self, db: Session, item: NewsItem) -> None:
        org_id = item.org_id
        photos = {m.photo_sha for m in item.media if m.photo_sha}
        videos = {m.video_id for m in item.media if m.video_id}
        db.delete(item)
        db.commit()
        self._forget(db, org_id, photos, videos)

    # --- Notification (§5) ---

    def _schedule(self, item_id: int) -> None:
        if self.session_factory is None or self.delay_seconds is None:
            return
        timer = threading.Timer(self.delay_seconds, self._send_later, args=(item_id,))
        timer.daemon = True
        timer.start()

    def _send_later(self, item_id: int) -> None:
        db = self.session_factory()
        try:
            self.send_notification(db, item_id)
        except Exception:  # noqa: BLE001 - a notification never breaks anything
            logger.exception("News notification not sent (item %s)", item_id)
        finally:
            db.close()

    def send_notification(self, db: Session, item_id: int) -> int:
        """Sends the item to every member of the organization's current
        season but its author, if it is still published and not sent yet.
        Returns how many members were notified."""
        item = db.get(NewsItem, item_id)
        if item is None or item.published_at is None or not item.notify or item.notified_at is not None:
            return 0
        item.notified_at = _now()
        db.commit()
        ecole = db.get(Ecole, item.org_id)
        title = ecole.nom if ecole else "Actualités"
        body = item.body if len(item.body) <= PREVIEW_CHARS else item.body[: PREVIEW_CHARS - 1].rstrip() + "…"
        season = saison_courante_id(db, item.org_id)
        with toutes_saisons(db):
            members = list(db.scalars(select(Compte).where(Compte.ecole_id == item.org_id, Compte.saison_id == season)))
        count = 0
        for member in members:
            if member.id == item.author_id or not can_read(member):
                continue
            try:
                self.notifications.envoyer_a_compte(db, member.id, title, body)
                count += 1
            except Exception:  # noqa: BLE001
                logger.exception("News notification not sent to account %s", member.id)
        return count
