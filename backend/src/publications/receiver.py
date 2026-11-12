"""HTTP routes of the Publications module (spec/modules/actualites.md §8,
§12.9), under /ecoles/{ecole_id}/publications/blogs/{blog_id}/… Reading:
every member, or only those with the blog's 🔒 right « Publier dans <blog> »
when it is not « visible par tout le monde ». The blogs themselves are set
by the Administrateur principal (Fonctionnalités, §12.3)."""

from __future__ import annotations

import base64
from collections.abc import Callable
from datetime import date

from comptes import Compte, rbac
from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session
from storage import FileTooLarge
from videos.schemas import VideoSortie

from db import get_db

from .instagram import InstagramError, InstagramRelay
from .links import LinkError
from .models import Blog, Category, Post
from .publications import InvalidBlog, InvalidMedia, Publications, can_publish, can_read, on_top
from .schemas import (
    BlogChange, BlogIn, BlogOut, CategoryIn, CategoryOut, CategoryRef, DocumentOut, FeedOut, InstagramIn,
    InstagramOut, LinkIn, LinkOut, LoginOut, MediaOut, PhotoOut, PostIn, PostOut, SettingsIn, SettingsOut, VideoIn,
)

BASE = "/ecoles/{ecole_id}/publications/blogs"
BLOG = BASE + "/{blog_id}"
POST = BLOG + "/posts/{post_id}"


def _out(client: Publications, db: Session, blog: Blog, post: Post, seen=None, me: int | None = None) -> PostOut:
    is_new = bool(seen is not None and post.published_at and post.published_at > seen and post.author_id != me)
    document = client.document(db, post)
    categories = []
    if blog.with_categories and post.category_id:
        category = db.get(Category, post.category_id)
        parent = db.get(Category, category.parent_id) if category.parent_id else None
        categories = [CategoryRef(id=c.id, name=c.name) for c in (parent, category) if c is not None]
    return PostOut(
        id=post.id, level=post.level if blog.with_levels else "normal", body=post.body,
        on_top_until=post.on_top_until, on_top=on_top(post, blog, date.today()), notify=post.notify,
        author_name=post.author_name, published_at=post.published_at, updated_at=post.updated_at, is_new=is_new,
        media=[
            MediaOut(photo=m.photo_sha, video=VideoSortie.model_validate(video) if video else None,
                     link=m.link_url, title=m.link_title)
            for m, video in client.media(db, post) if m.photo_sha or video or m.link_url
        ],
        document=DocumentOut(id=document.id, name=document.name) if document else None,
        title=post.title if blog.with_categories else None, categories=categories,
    )


class PublicationsReceiver:
    def __init__(self, client: Publications, instagram: InstagramRelay, app: FastAPI,
                 org_url: Callable[[Session, int | None], str] | None = None) -> None:
        self.client = client
        self.instagram = instagram
        # org_url(db, org_id): the address of the organization's app, where
        # « Se connecter avec Instagram » comes back.
        self.org_url = org_url
        app.get(BASE, response_model=list[BlogOut])(self.blogs)
        app.post(BASE, response_model=BlogOut, status_code=201)(self.create_blog)
        app.put(BLOG, response_model=BlogOut)(self.change_blog)
        app.delete(BLOG, status_code=204)(self.delete_blog)
        app.get(BLOG, response_model=FeedOut)(self.feed)
        app.post(BLOG + "/posts", response_model=PostOut, status_code=201)(self.create)
        app.post(BLOG + "/photos", response_model=PhotoOut, status_code=201)(self.upload_photo)
        app.post(BLOG + "/videos", response_model=VideoSortie, status_code=201)(self.add_video)
        app.post(BLOG + "/links", response_model=LinkOut, status_code=201)(self.add_link)
        app.get(BLOG + "/settings", response_model=SettingsOut)(self.settings)
        app.put(BLOG + "/settings", response_model=SettingsOut)(self.change_settings)
        app.get(BLOG + "/categories", response_model=list[CategoryOut])(self.categories)
        app.put(BLOG + "/categories/{category_id}", response_model=list[CategoryOut])(self.rename_category)
        app.get(BLOG + "/instagram", response_model=InstagramOut)(self.instagram_status)
        app.put(BLOG + "/instagram", response_model=InstagramOut)(self.instagram_link)
        app.delete(BLOG + "/instagram", response_model=InstagramOut)(self.instagram_unlink)
        app.post(BLOG + "/instagram/login", response_model=LoginOut)(self.instagram_login)
        # Public, and declared as is in the Meta app: kept from the module's
        # first name (`news`).
        app.get("/news/instagram/return")(self.instagram_return)
        app.put(POST, response_model=PostOut)(self.update)
        app.post(POST + "/unpublish", response_model=PostOut)(self.unpublish)
        app.delete(POST, status_code=204)(self.delete)
        app.get(POST + "/photos/{sha}")(self.photo)

    # --- Access ---

    def _blog(self, db: Session, ecole_id: int, blog_id: int) -> Blog:
        blog = self.client.blog(db, ecole_id, blog_id)
        if blog is None:
            raise HTTPException(status_code=404, detail="Blog introuvable")
        return blog

    def _reader(self, db: Session, appelant: Compte | None, ecole_id: int, blog_id: int) -> Blog:
        rbac.require_membre(appelant, ecole_id)
        blog = self._blog(db, ecole_id, blog_id)
        if not can_read(appelant, blog):
            raise HTTPException(status_code=403, detail=f"{blog.name} n'est pas visible")
        return blog

    def _publisher(self, db: Session, appelant: Compte | None, ecole_id: int, blog_id: int) -> Blog:
        rbac.require_membre(appelant, ecole_id)
        blog = self._blog(db, ecole_id, blog_id)
        if not can_publish(appelant, blog):
            raise HTTPException(status_code=403, detail=f"Réservé aux personnes qui publient dans {blog.name}")
        return blog

    def _post(self, db: Session, blog: Blog, post_id: int) -> Post:
        post = self.client.get(db, blog, post_id)
        if post is None:
            raise HTTPException(status_code=404, detail="Publication introuvable")
        return post

    # --- Blogs (§12.3) ---

    def _blog_out(self, db: Session, blog: Blog, appelant: Compte | None) -> BlogOut:
        reader = can_read(appelant, blog)
        return BlogOut(
            id=blog.id, name=blog.name, icon=blog.icon, with_levels=blog.with_levels,
            with_categories=blog.with_categories, can_read=reader, can_publish=can_publish(appelant, blog),
            open_app_on=reader and blog.open_app_on, has_posts=reader and self.client.has_posts(db, blog),
        )

    def blogs(self, ecole_id: int, db: Session = Depends(get_db), appelant: Compte = Depends(rbac.compte_appelant)):
        """Every blog, for its tab (`can_read`) and for Fonctionnalités."""
        rbac.require_membre(appelant, ecole_id)
        return [self._blog_out(db, b, appelant) for b in self.client.blogs(db, ecole_id)]

    def create_blog(self, ecole_id: int, data: BlogIn, db: Session = Depends(get_db),
                    appelant: Compte = Depends(rbac.compte_appelant)):
        rbac.require_owner(appelant, ecole_id)
        try:
            return self._blog_out(db, self.client.create_blog(db, ecole_id, data.name), appelant)
        except InvalidBlog as erreur:
            raise HTTPException(status_code=400, detail=str(erreur)) from erreur

    def change_blog(self, ecole_id: int, blog_id: int, data: BlogChange, db: Session = Depends(get_db),
                    appelant: Compte = Depends(rbac.compte_appelant)):
        rbac.require_owner(appelant, ecole_id)
        blog = self._blog(db, ecole_id, blog_id)
        try:
            return self._blog_out(db, self.client.change_blog(db, blog, **data.model_dump()), appelant)
        except InvalidBlog as erreur:
            raise HTTPException(status_code=400, detail=str(erreur)) from erreur

    def delete_blog(self, ecole_id: int, blog_id: int, db: Session = Depends(get_db),
                    appelant: Compte = Depends(rbac.compte_appelant)):
        rbac.require_owner(appelant, ecole_id)
        try:
            self.client.delete_blog(db, self._blog(db, ecole_id, blog_id))
        except InvalidBlog as erreur:
            raise HTTPException(status_code=409, detail=str(erreur)) from erreur

    # --- Posts ---

    def feed(self, ecole_id: int, blog_id: int, db: Session = Depends(get_db),
             appelant: Compte = Depends(rbac.compte_appelant)):
        """The posts everybody sees, and the drafts to those who publish;
        opening the blog clears « Nouveau »."""
        blog = self._reader(db, appelant, ecole_id, blog_id)
        me = appelant.id if appelant is not None else None
        seen = self.client.last_seen(db, me, blog) if me is not None else None
        items = [_out(self.client, db, blog, p, seen, me) for p in self.client.published(db, blog)]
        publisher = can_publish(appelant, blog)
        drafts = [_out(self.client, db, blog, p) for p in self.client.drafts(db, blog)] if publisher else []
        if me is not None:
            self.client.mark_seen(db, me, blog)
        return FeedOut(can_publish=publisher, media_first=blog.media_first, items=items, drafts=drafts)

    def create(self, ecole_id: int, blog_id: int, data: PostIn, db: Session = Depends(get_db),
               appelant: Compte = Depends(rbac.compte_appelant)):
        blog = self._publisher(db, appelant, ecole_id, blog_id)
        return _out(self.client, db, blog, self._save(db, blog, appelant, None, data))

    def update(self, ecole_id: int, blog_id: int, post_id: int, data: PostIn, db: Session = Depends(get_db),
               appelant: Compte = Depends(rbac.compte_appelant)):
        blog = self._publisher(db, appelant, ecole_id, blog_id)
        post = self._post(db, blog, post_id)
        return _out(self.client, db, blog, self._save(db, blog, appelant, post, data))

    def unpublish(self, ecole_id: int, blog_id: int, post_id: int, db: Session = Depends(get_db),
                  appelant: Compte = Depends(rbac.compte_appelant)):
        blog = self._publisher(db, appelant, ecole_id, blog_id)
        return _out(self.client, db, blog, self.client.unpublish(db, self._post(db, blog, post_id)))

    def delete(self, ecole_id: int, blog_id: int, post_id: int, db: Session = Depends(get_db),
               appelant: Compte = Depends(rbac.compte_appelant)):
        blog = self._publisher(db, appelant, ecole_id, blog_id)
        self.client.delete(db, self._post(db, blog, post_id))

    def _save(self, db: Session, blog: Blog, appelant: Compte | None, post: Post | None, data: PostIn):
        try:
            return self.client.save(db, blog, appelant, post, **data.model_dump())
        except InvalidMedia as erreur:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(erreur)) from erreur

    # --- Media ---

    def upload_photo(self, ecole_id: int, blog_id: int, fichier: UploadFile, db: Session = Depends(get_db),
                     appelant: Compte = Depends(rbac.compte_appelant)):
        self._publisher(db, appelant, ecole_id, blog_id)
        try:
            return PhotoOut(photo=self.client.store_photo(ecole_id, fichier.file))
        except FileTooLarge as erreur:
            raise HTTPException(status_code=413, detail="Photo trop lourde (25 Mo au plus)") from erreur
        except InvalidMedia as erreur:
            raise HTTPException(status_code=400, detail=str(erreur)) from erreur

    def add_link(self, ecole_id: int, blog_id: int, data: LinkIn, db: Session = Depends(get_db),
                 appelant: Compte = Depends(rbac.compte_appelant)):
        """A link for the carousel: its title and picture, read now (§3.3)."""
        self._publisher(db, appelant, ecole_id, blog_id)
        try:
            title, photo = self.client.read_link(ecole_id, data.url)
        except LinkError as erreur:
            raise HTTPException(status_code=400, detail=str(erreur)) from erreur
        preview = None
        if photo:
            preview = "data:image/jpeg;base64," + base64.b64encode(self.client.thumbnail(ecole_id, photo).read_bytes()).decode()
        return LinkOut(link=data.url.strip(), title=title, photo=photo, preview=preview)

    def add_video(self, ecole_id: int, blog_id: int, data: VideoIn, db: Session = Depends(get_db),
                  appelant: Compte = Depends(rbac.compte_appelant)):
        """« Publier » with a video: the upload (module Vidéos, by blocks)
        becomes a video, which the post then names."""
        blog = self._publisher(db, appelant, ecole_id, blog_id)
        if appelant is None:
            raise HTTPException(status_code=401, detail="Session requise")
        upload = self.client.videos.obtenir_televersement(db, data.upload_id)
        if upload is None or upload.ecole_id != ecole_id:
            raise HTTPException(status_code=404, detail="Envoi introuvable")
        return self.client.videos.finaliser(db, data.upload_id, nom=blog.name, uploaded_by=appelant.id)

    def photo(self, ecole_id: int, blog_id: int, post_id: int, sha: str, db: Session = Depends(get_db),
              appelant: Compte = Depends(rbac.compte_appelant)):
        blog = self._reader(db, appelant, ecole_id, blog_id)
        post = self._post(db, blog, post_id)
        if post.published_at is None and not can_publish(appelant, blog):
            raise HTTPException(status_code=404, detail="Publication introuvable")
        chemin = self.client.photo_path(post, sha)
        if chemin is None or not chemin.exists():
            raise HTTPException(status_code=404, detail="Pas de photo")
        return FileResponse(chemin, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=31536000, immutable"})

    # --- Categories (§12.6) ---

    def _tree(self, db: Session, blog: Blog) -> list[CategoryOut]:
        categories = self.client.categories(db, blog)
        counts = self.client.counts(db, blog)

        def level(parent_id):
            found = sorted((c for c in categories if c.parent_id == parent_id), key=lambda c: c.name.casefold())
            return [CategoryOut(id=c.id, name=c.name, count=counts.get(c.id, 0), children=level(c.id)) for c in found]

        return level(None)

    def categories(self, ecole_id: int, blog_id: int, db: Session = Depends(get_db),
                   appelant: Compte = Depends(rbac.compte_appelant)):
        blog = self._reader(db, appelant, ecole_id, blog_id)
        return self._tree(db, blog)

    def rename_category(self, ecole_id: int, blog_id: int, category_id: int, data: CategoryIn,
                        db: Session = Depends(get_db), appelant: Compte = Depends(rbac.compte_appelant)):
        """« Renommer »; the name of another category at the same level
        merges them. Returns the new tree."""
        blog = self._publisher(db, appelant, ecole_id, blog_id)
        category = self.client.category(db, blog, category_id)
        if category is None:
            raise HTTPException(status_code=404, detail="Catégorie introuvable")
        try:
            self.client.rename_category(db, blog, category, data.name)
        except InvalidBlog as erreur:
            raise HTTPException(status_code=400, detail=str(erreur)) from erreur
        return self._tree(db, blog)

    # --- Paramètres de <blog> (§12.5) ---

    def _settings_out(self, db: Session, blog: Blog) -> SettingsOut:
        return SettingsOut(
            open_app_on=blog.open_app_on, media_first=blog.media_first, visible_to_all=blog.visible_to_all,
            instagram_hashtag=self.instagram.hashtag(db, blog.org_id),
            instagram_publish=self.instagram.publishes(db, blog.org_id),
        )

    def settings(self, ecole_id: int, blog_id: int, db: Session = Depends(get_db),
                 appelant: Compte = Depends(rbac.compte_appelant)):
        return self._settings_out(db, self._publisher(db, appelant, ecole_id, blog_id))

    def change_settings(self, ecole_id: int, blog_id: int, data: SettingsIn, db: Session = Depends(get_db),
                        appelant: Compte = Depends(rbac.compte_appelant)):
        blog = self._publisher(db, appelant, ecole_id, blog_id)
        self.client.change_settings(db, blog, open_app_on=data.open_app_on, media_first=data.media_first,
                                    visible_to_all=data.visible_to_all)
        if data.instagram_hashtag is not None or data.instagram_publish is not None:
            self.instagram.change_settings(db, ecole_id, data.instagram_hashtag, data.instagram_publish)
        return self._settings_out(db, blog)

    # --- Instagram (§6 bis) ---

    def _instagram_out(self, db: Session, blog: Blog, link) -> InstagramOut:
        can_sign_in = self.instagram.app is not None
        if link is None:
            return InstagramOut(linked=False, can_sign_in=can_sign_in)
        target = self.instagram.blog_of(db, link)
        return InstagramOut(linked=True, username=link.username, last_sync_at=link.last_sync_at,
                            last_error=link.last_error, can_sign_in=can_sign_in,
                            elsewhere=target.name if target.id != blog.id else None)

    def instagram_status(self, ecole_id: int, blog_id: int, db: Session = Depends(get_db),
                         appelant: Compte = Depends(rbac.compte_appelant)):
        """The Instagram account relayed into a blog of the organization."""
        blog = self._publisher(db, appelant, ecole_id, blog_id)
        return self._instagram_out(db, blog, self.instagram.get(db, ecole_id))

    def instagram_link(self, ecole_id: int, blog_id: int, data: InstagramIn, db: Session = Depends(get_db),
                       appelant: Compte = Depends(rbac.compte_appelant)):
        blog = self._publisher(db, appelant, ecole_id, blog_id)
        try:
            return self._instagram_out(db, blog, self.instagram.link(db, ecole_id, appelant, data.token, blog.id))
        except InstagramError as erreur:
            raise HTTPException(status_code=400, detail=str(erreur)) from erreur

    def instagram_unlink(self, ecole_id: int, blog_id: int, db: Session = Depends(get_db),
                         appelant: Compte = Depends(rbac.compte_appelant)):
        blog = self._publisher(db, appelant, ecole_id, blog_id)
        self.instagram.unlink(db, ecole_id)
        return self._instagram_out(db, blog, None)

    def instagram_login(self, ecole_id: int, blog_id: int, db: Session = Depends(get_db),
                        appelant: Compte = Depends(rbac.compte_appelant)):
        """« Se connecter avec Instagram »: the address of Instagram's page."""
        blog = self._publisher(db, appelant, ecole_id, blog_id)
        try:
            return LoginOut(url=self.instagram.login_url(ecole_id, appelant, blog.id))
        except InstagramError as erreur:
            raise HTTPException(status_code=409, detail=str(erreur)) from erreur

    def instagram_return(self, state: str = "", code: str = "", error: str = "", db: Session = Depends(get_db)):
        """Back from Instagram (public route: `state`, signed by the server
        and valid 30 minutes, says which organization, who and which blog).
        Then back to the organization's address, where the person's session
        lives."""
        org_id, blog_id = self.instagram.origin_of(state)
        if error or not code:
            result = "annule"
        else:
            try:
                self.instagram.complete(db, code, state)
                result = "ok"
            except InstagramError:
                result = "erreur"
        base = self.org_url(db, org_id) if self.org_url is not None else ""
        back = f"{base.rstrip('/')}/?instagram={result}" + (f"&blog={blog_id}" if blog_id else "")
        return RedirectResponse(back, status_code=303)
