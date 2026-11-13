"""Tables of the Publications module (spec/modules/actualites.md §7 and §12.7).

An organization has one or more blogs (« Actus », « Techniques »…), each with
its own tab; a post belongs to one blog. Renamed from `news_*` on
12 November 2026 (migration f3b9d2a6c8e1), nothing lost."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base

IMPORTANT, NORMAL, BRIEF = "important", "normal", "brief"
LEVELS = (IMPORTANT, NORMAL, BRIEF)
ICONS = ("news", "books", "video", "cap", "star", "cup")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Blog(Base):
    """One blog of the organization: its tab, its right to publish, its
    settings (§12.3 in Fonctionnalités, §12.5 behind the ⋯ menu)."""

    __tablename__ = "pub_blogs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    icon: Mapped[str] = mapped_column(String(20), nullable=False, default="news")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    with_levels: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    with_categories: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # « L'appli affiche toujours … à son ouverture »: one blog at most.
    open_app_on: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # « En haut de chaque billet » : photos and videos above the text.
    media_first: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # « visibles par tout le monde »; off, only those who publish see it.
    visible_to_all: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Category(Base):
    """A category of a blog, or a sub-category (`parent_id`, one level).
    Exists while a post is filed in it (§12.6)."""

    __tablename__ = "pub_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    blog_id: Mapped[int] = mapped_column(ForeignKey("pub_blogs.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("pub_categories.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False)


class Post(Base):
    """One post (une actu, une technique). A draft has no `published_at`.
    Not tied to a season: it belongs to the organization."""

    __tablename__ = "pub_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id"), nullable=False, index=True)
    blog_id: Mapped[int] = mapped_column(ForeignKey("pub_blogs.id"), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(10), nullable=False, default=NORMAL)
    # Blog with categories: its name and its category (or sub-category).
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("pub_categories.id"), nullable=True, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # Important only: stays on top, in red, until this day included.
    on_top_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    notify: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # The Instagram post this one relays (§6 bis), so it comes in only once.
    instagram_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # Photos and videos: `media`, in order (a carousel, §3.3). One document.
    document_id: Mapped[int | None] = mapped_column(ForeignKey("doc_nodes.id"), nullable=True)
    # Set once the push notification has gone (10 s after publishing).
    notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # The member's record of the season it was written in; the first name is
    # kept so that the post still shows it once that season is over.
    author_id: Mapped[int | None] = mapped_column(ForeignKey("comptes.id"), nullable=True)
    author_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    media: Mapped[list[PostMedia]] = relationship(
        order_by="PostMedia.position", cascade="all, delete-orphan", lazy="selectin",
    )


class PostMedia(Base):
    """One photo, one video or one link of a post, at its place in the
    carousel (§3.3, Seb 8 and 9 November)."""

    __tablename__ = "pub_media"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("pub_posts.id", ondelete="CASCADE"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Photo: its sha256 in the publications storage (storage.py).
    photo_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    video_id: Mapped[int | None] = mapped_column(ForeignKey("videos.id"), nullable=True, index=True)
    # Link (YouTube or any site): its address and title; its picture, if
    # any, is kept as a photo (photo_sha).
    link_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    link_title: Mapped[str | None] = mapped_column(String(300), nullable=True)


class Seen(Base):
    """When a member last opened a blog (the « Nouveau » tag)."""

    __tablename__ = "pub_seen"

    compte_id: Mapped[int] = mapped_column(ForeignKey("comptes.id"), primary_key=True)
    blog_id: Mapped[int] = mapped_column(ForeignKey("pub_blogs.id", ondelete="CASCADE"), primary_key=True)
    seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class InstagramSettings(Base):
    """Which Instagram posts come in (Seb, 11 November). Kept apart from the
    link, so it can be set before linking. No row = the defaults."""

    __tablename__ = "pub_instagram_settings"

    org_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id"), primary_key=True)
    # Only the posts with this hashtag come in; empty: all of them.
    hashtag: Mapped[str] = mapped_column(String(100), nullable=False, default="", server_default="")
    # Off: the relayed posts arrive as drafts.
    publish: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())


class InstagramLink(Base):
    """The Instagram account whose new posts come into a blog (§6 bis).
    One per organization; the access key is kept encrypted."""

    __tablename__ = "pub_instagram"

    org_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id"), primary_key=True)
    # The blog where it was linked, where its posts arrive.
    blog_id: Mapped[int | None] = mapped_column(ForeignKey("pub_blogs.id"), nullable=True)
    token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    # Who linked it: the posts are signed with this first name.
    linked_by: Mapped[int | None] = mapped_column(ForeignKey("comptes.id"), nullable=True)
    linked_by_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    # Seb, 13 November: the member chosen to sign the posts instead (none:
    # whoever linked it).
    signed_by: Mapped[int | None] = mapped_column(ForeignKey("comptes.id"), nullable=True)
    signed_by_name: Mapped[str] = mapped_column(String(100), nullable=False, default="", server_default="")
    # Only posts published after this come in, not the whole history.
    linked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    token_refreshed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    # Linked through Meta's Unified Login (Seb, 11 November): the account's id
    # on graph.facebook.com, and a key that is never renewed.
    ig_user_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    refreshes: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

