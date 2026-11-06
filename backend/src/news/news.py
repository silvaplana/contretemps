"""What the news module does (spec/modules/actualites.md), without HTTP.

Every query filters by organization. The push notification leaves 10 s
after publishing, so that « Annuler » can still stop it (§5)."""

from __future__ import annotations

import logging
import threading
from datetime import date, datetime, timezone

from comptes import Compte
from ecoles.models import Ecole
from saisons.portee import toutes_saisons
from saisons.saisons import saison_courante_id
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import IMPORTANT, NewsItem, NewsSeen, NewsSettings

logger = logging.getLogger(__name__)

UNDO_SECONDS = 10
PREVIEW_CHARS = 100


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def on_top(item: NewsItem, today: date) -> bool:
    return item.level == IMPORTANT and item.on_top_until is not None and item.on_top_until >= today


class News:
    def __init__(self, notifications, session_factory=None, delay_seconds: float | None = UNDO_SECONDS) -> None:
        self.notifications = notifications
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
        settings = db.get(NewsSettings, org_id)
        if settings is None:
            db.add(NewsSettings(org_id=org_id, open_on_news=value))
        else:
            settings.open_on_news = value
        db.commit()

    # --- Writing ---

    def save(self, db: Session, org_id: int, author: Compte | None, item: NewsItem | None, *,
             level: str, body: str, on_top_until: date | None, notify: bool, publish: bool) -> NewsItem:
        """Creates (`item=None`) or changes an item. `publish` puts it in the
        feed, or back in the drafts."""
        if item is None:
            item = NewsItem(org_id=org_id, author_id=author.id if author else None,
                            author_name=author.prenom if author else "")
            db.add(item)
        item.level = level
        item.body = body.strip()
        item.on_top_until = on_top_until if level == IMPORTANT else None
        item.notify = notify
        newly_published = publish and item.published_at is None
        if publish and item.published_at is None:
            item.published_at = _now()
        if not publish:
            item.published_at = None
        db.commit()
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
        db.delete(item)
        db.commit()

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
            if member.id == item.author_id:
                continue
            try:
                self.notifications.envoyer_a_compte(db, member.id, title, body)
                count += 1
            except Exception:  # noqa: BLE001
                logger.exception("News notification not sent to account %s", member.id)
        return count
