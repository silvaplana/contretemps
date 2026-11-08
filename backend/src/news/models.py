"""Tables of the news module (spec/modules/actualites.md §7)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db import Base

IMPORTANT, NORMAL, BRIEF = "important", "normal", "brief"
LEVELS = (IMPORTANT, NORMAL, BRIEF)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class NewsItem(Base):
    """One news item. A draft has no `published_at`. Not tied to a season:
    it belongs to the organization."""

    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id"), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(10), nullable=False, default=NORMAL)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # Important only: stays on top, in red, until this day included.
    on_top_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    notify: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # At most one media (a photo or a video) and one document (§3.3).
    # Photo: its sha256 in the news storage (news/storage.py).
    photo_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # The Instagram post this item relays (§6 bis), so it comes in only once.
    instagram_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    video_id: Mapped[int | None] = mapped_column(ForeignKey("videos.id"), nullable=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("doc_nodes.id"), nullable=True)
    # Set once the push notification has gone (10 s after publishing).
    notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # The member's record of the season it was written in; the first name is
    # kept so that the item still shows it once that season is over.
    author_id: Mapped[int | None] = mapped_column(ForeignKey("comptes.id"), nullable=True)
    author_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


class NewsSeen(Base):
    """When a member last opened the news (the « Nouveau » tag)."""

    __tablename__ = "news_seen"

    compte_id: Mapped[int] = mapped_column(ForeignKey("comptes.id"), primary_key=True)
    seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class NewsSettings(Base):
    """Options of the Atelier. No row = the defaults."""

    __tablename__ = "news_settings"

    org_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id"), primary_key=True)
    open_on_news: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class NewsInstagram(Base):
    """The Instagram account whose new posts come into the news (§6 bis).
    One per organization; the access key is kept encrypted."""

    __tablename__ = "news_instagram"

    org_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id"), primary_key=True)
    token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    # Who linked it: the news items are signed with this first name.
    linked_by: Mapped[int | None] = mapped_column(ForeignKey("comptes.id"), nullable=True)
    linked_by_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    # Only posts published after this come in, not the whole history.
    linked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    token_refreshed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
