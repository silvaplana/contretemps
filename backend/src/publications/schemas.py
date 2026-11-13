"""Shapes of the Publications API (spec/modules/actualites.md §8, §12.9)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field
from videos.schemas import VideoSortie


class MediaIn(BaseModel):
    """One element of the carousel: a photo, a video or a link."""

    photo: str | None = Field(None, pattern=r"^[0-9a-f]{64}$")  # from POST …/photos or …/links
    video_id: int | None = None  # from POST …/videos
    link: str | None = Field(None, max_length=2000)  # from POST …/links; `photo` is its picture
    title: str | None = Field(None, max_length=300)


class MediaOut(BaseModel):
    photo: str | None = None
    video: VideoSortie | None = None
    link: str | None = None
    title: str | None = None


class LinkIn(BaseModel):
    url: str = Field(min_length=1, max_length=2000)


class LinkOut(BaseModel):
    link: str
    title: str
    photo: str | None = None  # the site's picture, kept like a photo
    preview: str | None = None  # the same picture as a data: URL, for the editor


class PollIn(BaseModel):
    # Sondage (Seb, 13 November): 2 to 10 answers, checked by the service.
    question: str = Field(max_length=200)
    multiple: bool = False
    options: list[str] = Field(max_length=10)


class PollOptionOut(BaseModel):
    id: int
    label: str
    voters: list[str]  # first names, in voting order
    mine: bool = False


class PollOut(BaseModel):
    question: str
    multiple: bool
    options: list[PollOptionOut]
    voters: int  # people who answered


class VoteIn(BaseModel):
    options: list[int] = Field(default_factory=list, max_length=10)  # empty: remove my vote


class PostIn(BaseModel):
    level: Literal["important", "normal", "brief"] = "normal"
    body: str = Field("", max_length=5000)  # may be empty when there is a media or a document
    on_top_until: date | None = None
    notify: bool = False
    publish: bool = True
    media: list[MediaIn] = Field(default_factory=list, max_length=10)  # in order
    document_id: int | None = None  # a file of Docs
    # Blog with categories (§12.6): its name, its category by name (chosen or
    # new), and an optional sub-category.
    title: str | None = Field(None, max_length=200)
    category: str | None = Field(None, max_length=60)
    subcategory: str | None = Field(None, max_length=60)
    poll: PollIn | None = None


class DocumentOut(BaseModel):
    id: int
    name: str


class CategoryRef(BaseModel):
    id: int
    name: str


class ReactionOut(BaseModel):
    name: str
    emoji: str
    mine: bool = False


class ReactionIn(BaseModel):
    emoji: str | None = None  # None: remove mine


class PostOut(BaseModel):
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
    # Blog with categories: its name, its category, then its sub-category.
    title: str | None = None
    categories: list[CategoryRef] = []
    # One per person, the oldest first (Seb, 13 November).
    reactions: list[ReactionOut] = []
    poll: PollOut | None = None


class PhotoOut(BaseModel):
    photo: str


class VideoIn(BaseModel):
    upload_id: str


class FeedOut(BaseModel):
    can_publish: bool
    media_first: bool = False  # photos and videos on top of each post
    items: list[PostOut]
    # « Mes brouillons », for those who publish (§12.5).
    drafts: list[PostOut] = []


class BlogOut(BaseModel):
    id: int
    name: str
    icon: str
    with_levels: bool
    with_categories: bool
    # Sees its tab (« visible par tout le monde », or publishes in it).
    can_read: bool
    can_publish: bool
    # The app opens on it (one blog at most), when it has a post.
    open_app_on: bool
    has_posts: bool
    # Newest published post (§6: opened twice on it, the app stops opening there).
    latest_post: int | None = None


class BlogIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)


class BlogChange(BaseModel):
    # Fonctionnalités (§12.3): only what is given changes.
    name: str | None = Field(None, min_length=1, max_length=60)
    icon: str | None = None
    with_levels: bool | None = None
    with_categories: bool | None = None


class SettingsOut(BaseModel):
    """« Paramètres de <blog> » (§12.5)."""

    open_app_on: bool
    media_first: bool = False
    # « visibles par tout le monde »; off, only those who publish.
    visible_to_all: bool = True
    # Instagram, the organization's (§6 bis): only the posts with #this
    # (empty: all), and published at once (else: drafts).
    instagram_hashtag: str = ""
    instagram_publish: bool = True


class SettingsIn(BaseModel):
    # Only what is given changes.
    open_app_on: bool | None = None
    media_first: bool | None = None
    visible_to_all: bool | None = None
    instagram_hashtag: str | None = Field(None, max_length=100)
    instagram_publish: bool | None = None


class CategoryOut(BaseModel):
    """A category with how many posts are filed in it, and its
    sub-categories (§12.6), in alphabetical order."""

    id: int
    name: str
    count: int
    children: list[CategoryOut] = []


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)


class InstagramIn(BaseModel):
    token: str = Field(min_length=20, max_length=1000)


class SignerIn(BaseModel):
    member_id: int


class PersonOut(BaseModel):
    id: int
    name: str


class LoginOut(BaseModel):
    url: str


class InstagramOut(BaseModel):
    linked: bool
    username: str | None = None
    # The blog where its posts arrive, when it is not this one (§12.5).
    elsewhere: str | None = None
    last_sync_at: datetime | None = None
    last_error: str | None = None
    # The member whose first name signs the relayed posts.
    signer_id: int | None = None
    can_sign_in: bool = False  # « Se connecter avec Instagram » (Meta app on the server)
