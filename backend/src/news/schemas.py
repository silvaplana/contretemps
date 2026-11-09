"""Shapes of the news API (spec/modules/actualites.md §8)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field
from videos.schemas import VideoSortie


class MediaIn(BaseModel):
    """One element of the carousel: a photo or a video."""

    photo: str | None = Field(None, pattern=r"^[0-9a-f]{64}$")  # from POST …/news/photos
    video_id: int | None = None  # from POST …/news/videos


class MediaOut(BaseModel):
    photo: str | None = None
    video: VideoSortie | None = None


class NewsIn(BaseModel):
    level: Literal["important", "normal", "brief"] = "normal"
    body: str = Field(min_length=1, max_length=5000)
    on_top_until: date | None = None
    notify: bool = False
    publish: bool = True
    media: list[MediaIn] = Field(default_factory=list, max_length=10)  # in order
    document_id: int | None = None  # a file of Docs


class DocumentOut(BaseModel):
    id: int
    name: str


class NewsOut(BaseModel):
    id: int
    level: str
    body: str
    on_top_until: date | None
    on_top: bool
    notify: bool
    author_name: str
    published_at: datetime | None
    updated_at: datetime
    is_new: bool = False
    media: list[MediaOut] = []
    document: DocumentOut | None = None


class PhotoOut(BaseModel):
    photo: str


class VideoIn(BaseModel):
    upload_id: str


class FeedOut(BaseModel):
    can_publish: bool
    media_first: bool = False  # photos and videos on top of each item
    items: list[NewsOut]


class SettingsOut(BaseModel):
    open_on_news: bool
    media_first: bool = False
    # Sees the Actus tab (right « Voir les actualités » while in test).
    can_read: bool = True
    # Ticks who sees the news (administrateur principal, Super User).
    can_choose_readers: bool = False


class ReaderOut(BaseModel):
    id: int
    name: str
    reads: bool
    publishes: bool


class ReaderIn(BaseModel):
    reads: bool


class SettingsIn(BaseModel):
    # Only what is given changes.
    open_on_news: bool | None = None
    media_first: bool | None = None


class InstagramIn(BaseModel):
    token: str = Field(min_length=20, max_length=1000)


class LoginOut(BaseModel):
    url: str


class InstagramOut(BaseModel):
    linked: bool
    username: str | None = None
    last_sync_at: datetime | None = None
    last_error: str | None = None
    can_sign_in: bool = False  # « Se connecter avec Instagram » (Meta app on the server)
