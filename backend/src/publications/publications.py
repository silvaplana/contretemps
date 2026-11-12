"""What the Publications module does (spec/modules/actualites.md), without
HTTP: the blogs of an organization (« Actus », « Techniques »…), their posts,
their categories.

Every query filters by organization, then by blog. The push notification
leaves 10 s after publishing, so that « Annuler » can still stop it (§5)."""

from __future__ import annotations

import io
import logging
import threading
import unicodedata
from datetime import date, datetime, timezone

from typing import BinaryIO

from comptes import Compte, roles
from documents.models import DocNode
from ecoles.models import Ecole
from groups import rights
from registry import Right
from saisons.portee import toutes_saisons
from saisons.saisons import saison_courante_id
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from storage import FileTooLarge, LocalStorage, make_thumbnail
from videos import Videos
from videos.models import Video

from . import links
from .models import BRIEF, ICONS, IMPORTANT, NORMAL, Blog, Category, InstagramLink, Post, PostMedia, Seen
from .storage import DISPLAY_SIZE

logger = logging.getLogger(__name__)

UNDO_SECONDS = 10
MAX_MEDIA = 10  # like an Instagram carousel
PREVIEW_CHARS = 100
DEFAULT_BLOG = "Actus"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalized(name: str) -> str:
    """« Clés » = « cles » (§12.6): no case, no accents."""
    decomposed = unicodedata.normalize("NFKD", name.strip().casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def publish_right(blog_id: int) -> str:
    """The 🔒 right of a blog (§12.4), one per blog."""
    return f"publications.publish.{blog_id}"


def right_label(blog: Blog) -> str:
    return f"Publier dans {blog.name}"


def blogs_of(db: Session, org_id: int) -> list[Blog]:
    """The organization's blogs, in the order of their tabs. A new
    organization gets « Actus » on its first visit (§12.2)."""
    blogs = list(db.scalars(select(Blog).where(Blog.org_id == org_id).order_by(Blog.position, Blog.id)))
    if not blogs:
        blog = Blog(org_id=org_id, name=DEFAULT_BLOG, icon="news", position=0, with_levels=True,
                    with_categories=False, open_app_on=True, media_first=False, visible_to_all=True)
        db.add(blog)
        db.commit()
        blogs = [blog]
    return blogs


def org_rights(db: Session, org_id: int) -> list[Right]:
    """The rights of this organization's blogs (spec/core.md §11.1),
    labels read now: renaming a blog renames its right."""
    return [Right(publish_right(b.id), right_label(b)) for b in blogs_of(db, org_id)]


def can_publish(compte: Compte | None, blog: Blog) -> bool:
    # `None`: rights switched off (tests, see tests/conftest.py).
    return compte is None or roles.has_right(compte, publish_right(blog.id))


def can_read(compte: Compte | None, blog: Blog) -> bool:
    """Everybody, or only those who publish when the blog is not
    « visible par tout le monde » (§2 bis)."""
    return blog.visible_to_all or can_publish(compte, blog)


def on_top(post: Post, blog: Blog, today: date) -> bool:
    return (blog.with_levels and post.level == IMPORTANT and post.on_top_until is not None
            and post.on_top_until >= today)


class InvalidMedia(ValueError):
    """A photo, video or document that cannot go in this post."""


class InvalidBlog(ValueError):
    """A blog name, category or change that is refused."""


class Publications:
    def __init__(self, notifications, storage: LocalStorage, videos: Videos, session_factory=None,
                 delay_seconds: float | None = UNDO_SECONDS) -> None:
        self.notifications = notifications
        self.storage = storage
        self.videos = videos
        # A video deleted elsewhere (Usage panel) leaves its post.
        videos.quand_supprimee(self._video_deleted)
        videos.rubrique("Publications", lambda db: set(db.scalars(select(PostMedia.video_id).where(PostMedia.video_id.is_not(None)))))
        # Where the delayed notification opens its own session; None (tests):
        # nothing is scheduled, `send_notification` is called by hand.
        self.session_factory = session_factory
        self.delay_seconds = delay_seconds

    # --- Blogs (§12.2, §12.3) ---

    def blogs(self, db: Session, org_id: int) -> list[Blog]:
        return blogs_of(db, org_id)

    def blog(self, db: Session, org_id: int, blog_id: int) -> Blog | None:
        blog = db.get(Blog, blog_id)
        return blog if blog is not None and blog.org_id == org_id else None

    def _check_name(self, db: Session, org_id: int, name: str, blog_id: int | None = None) -> str:
        name = " ".join(name.split())
        if not name:
            raise InvalidBlog("Donnez un nom")
        if any(normalized(b.name) == normalized(name) and b.id != blog_id for b in self.blogs(db, org_id)):
            raise InvalidBlog(f"« {name} » existe déjà")
        return name

    def create_blog(self, db: Session, org_id: int, name: str) -> Blog:
        """« + Ajouter un blog »: no categories, no levels, logo journal."""
        name = self._check_name(db, org_id, name)
        position = max((b.position for b in self.blogs(db, org_id)), default=-1) + 1
        blog = Blog(org_id=org_id, name=name, icon="news", position=position, with_levels=False,
                    with_categories=False, open_app_on=False, media_first=False, visible_to_all=True)
        db.add(blog)
        db.commit()
        db.refresh(blog)
        return blog

    def change_blog(self, db: Session, blog: Blog, *, name: str | None = None, icon: str | None = None,
                    with_levels: bool | None = None, with_categories: bool | None = None) -> Blog:
        """Each setting of Fonctionnalités, saved at once. Switching off
        categories or levels erases nothing (§12.3)."""
        if name is not None:
            blog.name = self._check_name(db, blog.org_id, name, blog.id)
            rights.rename(db, blog.org_id, publish_right(blog.id), right_label(blog))
        if icon is not None:
            if icon not in ICONS:
                raise InvalidBlog("Logo inconnu")
            blog.icon = icon
        if with_levels is not None:
            blog.with_levels = with_levels
        if with_categories is not None:
            blog.with_categories = with_categories
        db.commit()
        db.refresh(blog)
        return blog

    def delete_blog(self, db: Session, blog: Blog) -> None:
        """Only an empty blog, never the last one (§12.10); its right goes
        with it."""
        if self.has_posts(db, blog, drafts=True):
            raise InvalidBlog("Supprimez d'abord ses publications")
        if len(self.blogs(db, blog.org_id)) == 1:
            raise InvalidBlog("Il faut garder au moins un blog")
        rights.forget(db, blog.org_id, publish_right(blog.id))
        db.execute(delete(Seen).where(Seen.blog_id == blog.id))
        db.execute(delete(Category).where(Category.blog_id == blog.id))
        link = db.get(InstagramLink, blog.org_id)
        if link is not None and link.blog_id == blog.id:
            link.blog_id = None
        db.delete(blog)
        db.commit()

    def has_posts(self, db: Session, blog: Blog, drafts: bool = False) -> bool:
        query = select(Post.id).where(Post.org_id == blog.org_id, Post.blog_id == blog.id)
        if not drafts:
            query = query.where(Post.published_at.is_not(None))
        return db.scalar(query.limit(1)) is not None

    def latest_post(self, db: Session, blog: Blog) -> int | None:
        """The newest published post: the app stops opening on a blog it
        already opened twice on with the same newest post (§6)."""
        return db.scalar(
            select(Post.id)
            .where(Post.org_id == blog.org_id, Post.blog_id == blog.id, Post.published_at.is_not(None))
            .order_by(Post.published_at.desc(), Post.id.desc())
            .limit(1)
        )

    def change_settings(self, db: Session, blog: Blog, *, open_app_on: bool | None = None,
                        media_first: bool | None = None, visible_to_all: bool | None = None) -> Blog:
        """« Paramètres de <blog> » (§12.5). The app opens on one blog at
        most: switching it on here switches it off in the others."""
        if open_app_on:
            for other in self.blogs(db, blog.org_id):
                other.open_app_on = False
        if open_app_on is not None:
            blog.open_app_on = open_app_on
        if media_first is not None:
            blog.media_first = media_first
        if visible_to_all is not None:
            blog.visible_to_all = visible_to_all
        db.commit()
        db.refresh(blog)
        return blog

    # --- Reading ---

    def get(self, db: Session, blog: Blog, post_id: int) -> Post | None:
        post = db.get(Post, post_id)
        return post if post is not None and post.org_id == blog.org_id and post.blog_id == blog.id else None

    def published(self, db: Session, blog: Blog, today: date | None = None) -> list[Post]:
        """The feed: Important posts still on top, then everything else,
        newest first (§3.2)."""
        today = today or date.today()
        posts = list(db.scalars(
            select(Post)
            .where(Post.org_id == blog.org_id, Post.blog_id == blog.id, Post.published_at.is_not(None))
            .order_by(Post.published_at.desc(), Post.id.desc())
        ))
        return [p for p in posts if on_top(p, blog, today)] + [p for p in posts if not on_top(p, blog, today)]

    def drafts(self, db: Session, blog: Blog) -> list[Post]:
        """« Mes brouillons », newest first (§12.5)."""
        return list(db.scalars(
            select(Post).where(Post.org_id == blog.org_id, Post.blog_id == blog.id, Post.published_at.is_(None))
            .order_by(Post.updated_at.desc(), Post.id.desc())
        ))

    def last_seen(self, db: Session, compte_id: int, blog: Blog) -> datetime | None:
        seen = db.get(Seen, (compte_id, blog.id))
        return seen.seen_at if seen else None

    def mark_seen(self, db: Session, compte_id: int, blog: Blog) -> None:
        seen = db.get(Seen, (compte_id, blog.id))
        if seen is None:
            db.add(Seen(compte_id=compte_id, blog_id=blog.id, seen_at=_now()))
        else:
            seen.seen_at = _now()
        db.commit()

    # --- Categories (§12.6) ---

    def categories(self, db: Session, blog: Blog) -> list[Category]:
        return list(db.scalars(select(Category).where(Category.blog_id == blog.id)))

    def category(self, db: Session, blog: Blog, category_id: int) -> Category | None:
        category = db.get(Category, category_id)
        return category if category is not None and category.blog_id == blog.id else None

    def counts(self, db: Session, blog: Blog) -> dict[int, int]:
        """How many posts (drafts too) are filed directly in each category."""
        rows = db.execute(
            select(Post.category_id, func.count(Post.id))
            .where(Post.org_id == blog.org_id, Post.blog_id == blog.id, Post.category_id.is_not(None))
            .group_by(Post.category_id)
        )
        return {category_id: count for category_id, count in rows}

    def _find_or_create(self, db: Session, blog: Blog, name: str, parent: Category | None) -> Category:
        name = " ".join(name.split())[:60]
        parent_id = parent.id if parent else None
        for c in self.categories(db, blog):
            if c.parent_id == parent_id and normalized(c.name) == normalized(name):
                return c
        category = Category(blog_id=blog.id, parent_id=parent_id, name=name)
        db.add(category)
        db.flush()
        return category

    def _filing(self, db: Session, blog: Blog, category: str | None, subcategory: str | None) -> Category:
        if not (category or "").strip():
            raise InvalidMedia("Choisissez une catégorie")
        top = self._find_or_create(db, blog, category, None)
        return self._find_or_create(db, blog, subcategory, top) if (subcategory or "").strip() else top

    def _prune(self, db: Session, blog: Blog) -> None:
        """A category lives while a post is filed in it (§12.6)."""
        used = set(self.counts(db, blog))
        categories = self.categories(db, blog)
        for c in categories:
            if c.parent_id is not None and c.id not in used:
                db.delete(c)
        db.flush()
        children = {c.parent_id for c in self.categories(db, blog) if c.parent_id is not None}
        for c in categories:
            if c.parent_id is None and c.id not in used and c.id not in children:
                db.delete(c)
        db.commit()

    def rename_category(self, db: Session, blog: Blog, category: Category, name: str) -> Category:
        """The name of an existing category at the same level merges the
        two (§12.6)."""
        name = " ".join(name.split())[:60]
        if not name:
            raise InvalidBlog("Donnez un nom")
        twin = next((c for c in self.categories(db, blog) if c.id != category.id and c.parent_id == category.parent_id
                     and normalized(c.name) == normalized(name)), None)
        if twin is None:
            category.name = name
            db.commit()
            return category
        self._merge(db, blog, category, twin)
        self._prune(db, blog)
        return twin

    def _merge(self, db: Session, blog: Blog, source: Category, target: Category) -> None:
        for post in db.scalars(select(Post).where(Post.blog_id == blog.id, Post.category_id == source.id)):
            post.category_id = target.id
        for child in [c for c in self.categories(db, blog) if c.parent_id == source.id]:
            twin = next((c for c in self.categories(db, blog) if c.parent_id == target.id
                         and normalized(c.name) == normalized(child.name)), None)
            if twin is None:
                child.parent_id = target.id
            else:
                self._merge(db, blog, child, twin)
        db.flush()
        db.delete(source)
        db.flush()

    # --- Media (§3.3) ---

    def store_photo(self, org_id: int, source: BinaryIO) -> str:
        """Keeps a photo sent from the editor; returns its sha256, which
        the post then names. Raises InvalidMedia if it is not an image."""
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

    def photo_path(self, post: Post, sha: str):
        """The JPEG shown in the post (at most 1600 px), if this post has it."""
        if not any(m.photo_sha == sha for m in post.media):
            return None
        return self.storage.thumbnail_path(post.org_id, sha)

    def media(self, db: Session, post: Post) -> list[tuple[PostMedia, Video | None]]:
        """Each media of the post, in order, with its video. A video
        belongs to a season; the post outlives it."""
        with toutes_saisons(db):
            videos = {m.video_id: db.get(Video, m.video_id) for m in post.media if m.video_id}
        return [(m, videos.get(m.video_id)) for m in post.media]

    def document(self, db: Session, post: Post) -> DocNode | None:
        if post.document_id is None:
            return None
        node = db.get(DocNode, post.document_id)
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
        """Deletes the photos no post names any more, and the videos given."""
        for sha in photos:
            named = db.scalar(
                select(PostMedia.id).join(Post, Post.id == PostMedia.post_id)
                .where(Post.org_id == org_id, PostMedia.photo_sha == sha)
            )
            if named is None:
                self.storage.delete(org_id, sha)
        if videos:
            with toutes_saisons(db):
                for video_id in videos:
                    self.videos.delete(db, video_id)

    def _video_deleted(self, db: Session, video_id: int) -> None:
        for media in db.scalars(select(PostMedia).where(PostMedia.video_id == video_id)):
            db.delete(media)

    # --- Writing ---

    def save(self, db: Session, blog: Blog, author: Compte | None, post: Post | None, *,
             level: str, body: str, on_top_until: date | None, notify: bool, publish: bool,
             media: list[dict] | None = None, document_id: int | None = None, title: str | None = None,
             category: str | None = None, subcategory: str | None = None) -> Post:
        """Creates (`post=None`) or changes a post. `media`: its photos and
        videos in order, each {"photo": sha}, {"video_id": id} or
        {"link": url, "title": …, "photo": sha of its picture}. `publish`
        puts it in the feed, or back in the drafts. A brief has no media.
        A blog without levels keeps the level a post had; a blog with
        categories asks for a name and a category (§12.6). Raises
        InvalidMedia."""
        org_id = blog.org_id
        if not blog.with_levels:
            level = post.level if post else NORMAL
            on_top_until = post.on_top_until if post else None
        media = [] if level == BRIEF or media is None else media
        if level == BRIEF:
            document_id = None
        if not body.strip() and not media and not document_id:
            # Seb, 10 November: a photo alone is a post; nothing at all is not.
            raise InvalidMedia("Écrivez un texte ou ajoutez une photo, une vidéo, un lien ou un document")
        if blog.with_categories and not (title or "").strip():
            raise InvalidMedia("Donnez un nom")
        self._check_media(db, org_id, media, document_id)
        filing = self._filing(db, blog, category, subcategory) if blog.with_categories else None
        old_photos = {m.photo_sha for m in post.media if m.photo_sha} if post else set()
        old_videos = {m.video_id for m in post.media if m.video_id} if post else set()
        if post is None:
            post = Post(org_id=org_id, blog_id=blog.id, author_id=author.id if author else None,
                        author_name=author.prenom if author else "")
            db.add(post)
        if blog.with_categories:
            post.title = " ".join(title.split())[:200]
            post.category_id = filing.id
        post.level = level
        post.body = body.strip()
        post.on_top_until = on_top_until if level == IMPORTANT else None
        post.notify = notify
        post.media = [
            PostMedia(position=i, photo_sha=m.get("photo"), video_id=m.get("video_id"),
                      link_url=m.get("link"), link_title=(m.get("title") or "")[:300] if m.get("link") else None)
            for i, m in enumerate(media)
        ]
        post.document_id = document_id
        newly_published = publish and post.published_at is None
        if publish and post.published_at is None:
            post.published_at = _now()
        if not publish:
            post.published_at = None
        db.commit()
        self._prune(db, blog)
        self._forget(db, org_id, old_photos - {m.get("photo") for m in media},
                     old_videos - {m.get("video_id") for m in media})
        db.refresh(post)
        if newly_published and notify and post.notified_at is None:
            self._schedule(post.id)
        return post

    def unpublish(self, db: Session, post: Post) -> Post:
        """« Annuler » right after Publier: back to the drafts, and the
        notification, not sent yet, will not leave."""
        post.published_at = None
        db.commit()
        db.refresh(post)
        return post

    def delete(self, db: Session, post: Post) -> None:
        org_id = post.org_id
        blog = db.get(Blog, post.blog_id)
        photos = {m.photo_sha for m in post.media if m.photo_sha}
        videos = {m.video_id for m in post.media if m.video_id}
        db.delete(post)
        db.commit()
        self._prune(db, blog)
        self._forget(db, org_id, photos, videos)

    # --- Notification (§5) ---

    def _schedule(self, post_id: int) -> None:
        if self.session_factory is None or self.delay_seconds is None:
            return
        timer = threading.Timer(self.delay_seconds, self._send_later, args=(post_id,))
        timer.daemon = True
        timer.start()

    def _send_later(self, post_id: int) -> None:
        db = self.session_factory()
        try:
            self.send_notification(db, post_id)
        except Exception:  # noqa: BLE001 - a notification never breaks anything
            logger.exception("Publication notification not sent (post %s)", post_id)
        finally:
            db.close()

    def send_notification(self, db: Session, post_id: int) -> int:
        """Sends the post to every member of the organization's current
        season who reads the blog, but its author, if it is still published
        and not sent yet. Returns how many members were notified."""
        post = db.get(Post, post_id)
        if post is None or post.published_at is None or not post.notify or post.notified_at is not None:
            return 0
        post.notified_at = _now()
        db.commit()
        blog = db.get(Blog, post.blog_id)
        ecole = db.get(Ecole, post.org_id)
        title = ecole.nom if ecole else blog.name
        text = post.body if len(post.body) <= PREVIEW_CHARS else post.body[: PREVIEW_CHARS - 1].rstrip() + "…"
        if blog.with_categories and post.title:
            text = f"{post.title} · {text}" if text else post.title
        text = text or f"Nouveau dans {blog.name}"  # a photo without text
        season = saison_courante_id(db, post.org_id)
        with toutes_saisons(db):
            members = list(db.scalars(select(Compte).where(Compte.ecole_id == post.org_id, Compte.saison_id == season)))
        count = 0
        for member in members:
            if member.id == post.author_id or not can_read(member, blog):
                continue
            try:
                self.notifications.envoyer_a_compte(db, member.id, title, text)
                count += 1
            except Exception:  # noqa: BLE001
                logger.exception("Publication notification not sent to account %s", member.id)
        return count
