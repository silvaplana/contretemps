"""HTTP routes of the news module (spec/modules/actualites.md §8). Reading:
every member, or only those with « 🔒 Publier les actualités »
(`news.publish`) when the news are not « visibles par tout le monde »."""

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

from .models import NewsItem
from .instagram import InstagramError, InstagramRelay
from .links import LinkError
from .news import PUBLISH, InvalidMedia, News, can_publish, on_top
from .schemas import (
    DocumentOut, FeedOut, InstagramIn, InstagramOut, LinkIn, LinkOut, LoginOut, MediaOut, NewsIn, NewsOut, PhotoOut,
    SettingsIn, SettingsOut, VideoIn,
)

__all__ = ["PUBLISH", "NewsReceiver"]


def _out(client: News, db: Session, item: NewsItem, seen=None, me: int | None = None) -> NewsOut:
    is_new = bool(seen is not None and item.published_at and item.published_at > seen and item.author_id != me)
    document = client.document(db, item)
    return NewsOut(
        id=item.id, level=item.level, body=item.body, on_top_until=item.on_top_until,
        on_top=on_top(item, date.today()), notify=item.notify, author_name=item.author_name,
        published_at=item.published_at, updated_at=item.updated_at, is_new=is_new,
        media=[
            MediaOut(photo=m.photo_sha, video=VideoSortie.model_validate(video) if video else None,
                     link=m.link_url, title=m.link_title)
            for m, video in client.media(db, item) if m.photo_sha or video or m.link_url
        ],
        document=DocumentOut(id=document.id, name=document.name) if document else None,
    )


class NewsReceiver:
    def __init__(self, client: News, instagram: InstagramRelay, app: FastAPI,
                 org_url: Callable[[Session, int | None], str] | None = None) -> None:
        self.client = client
        self.instagram = instagram
        # org_url(db, org_id): the address of the organization's app, where
        # « Se connecter avec Instagram » comes back.
        self.org_url = org_url
        app.get("/ecoles/{ecole_id}/news", response_model=FeedOut)(self.feed)
        app.get("/ecoles/{ecole_id}/news/atelier", response_model=list[NewsOut])(self.workshop)
        app.post("/ecoles/{ecole_id}/news", response_model=NewsOut, status_code=201)(self.create)
        app.post("/ecoles/{ecole_id}/news/photos", response_model=PhotoOut, status_code=201)(self.upload_photo)
        app.post("/ecoles/{ecole_id}/news/videos", response_model=VideoSortie, status_code=201)(self.add_video)
        app.post("/ecoles/{ecole_id}/news/links", response_model=LinkOut, status_code=201)(self.add_link)
        app.get("/ecoles/{ecole_id}/news/settings", response_model=SettingsOut)(self.settings)
        app.put("/ecoles/{ecole_id}/news/settings", response_model=SettingsOut)(self.change_settings)
        app.get("/ecoles/{ecole_id}/news/instagram", response_model=InstagramOut)(self.instagram_status)
        app.put("/ecoles/{ecole_id}/news/instagram", response_model=InstagramOut)(self.instagram_link)
        app.delete("/ecoles/{ecole_id}/news/instagram", response_model=InstagramOut)(self.instagram_unlink)
        app.post("/ecoles/{ecole_id}/news/instagram/login", response_model=LoginOut)(self.instagram_login)
        app.get("/news/instagram/return")(self.instagram_return)
        app.put("/ecoles/{ecole_id}/news/{item_id}", response_model=NewsOut)(self.update)
        app.post("/ecoles/{ecole_id}/news/{item_id}/unpublish", response_model=NewsOut)(self.unpublish)
        app.delete("/ecoles/{ecole_id}/news/{item_id}", status_code=204)(self.delete)
        app.get("/ecoles/{ecole_id}/news/{item_id}/photos/{sha}")(self.photo)

    def _instagram_out(self, link) -> InstagramOut:
        can_sign_in = self.instagram.app is not None
        if link is None:
            return InstagramOut(linked=False, can_sign_in=can_sign_in)
        return InstagramOut(linked=True, username=link.username, last_sync_at=link.last_sync_at,
                            last_error=link.last_error, can_sign_in=can_sign_in)

    def instagram_status(self, ecole_id: int, db: Session = Depends(get_db),
                         appelant: Compte = Depends(rbac.compte_appelant)):
        """The Instagram account relayed into the news (§6 bis)."""
        self._publisher(appelant, ecole_id)
        return self._instagram_out(self.instagram.get(db, ecole_id))

    def instagram_link(self, ecole_id: int, data: InstagramIn, db: Session = Depends(get_db),
                       appelant: Compte = Depends(rbac.compte_appelant)):
        self._publisher(appelant, ecole_id)
        try:
            return self._instagram_out(self.instagram.link(db, ecole_id, appelant, data.token))
        except InstagramError as erreur:
            raise HTTPException(status_code=400, detail=str(erreur)) from erreur

    def instagram_unlink(self, ecole_id: int, db: Session = Depends(get_db),
                         appelant: Compte = Depends(rbac.compte_appelant)):
        self._publisher(appelant, ecole_id)
        self.instagram.unlink(db, ecole_id)
        return self._instagram_out(None)

    def instagram_login(self, ecole_id: int, appelant: Compte = Depends(rbac.compte_appelant)):
        """« Se connecter avec Instagram »: the address of Instagram's page."""
        self._publisher(appelant, ecole_id)
        try:
            return LoginOut(url=self.instagram.login_url(ecole_id, appelant))
        except InstagramError as erreur:
            raise HTTPException(status_code=409, detail=str(erreur)) from erreur

    def instagram_return(self, state: str = "", code: str = "", error: str = "", db: Session = Depends(get_db)):
        """Back from Instagram (public route: `state`, signed by the server
        and valid 30 minutes, says which organization and who). Then back to
        the organization's address, where the person's session lives."""
        org_id = self.instagram.org_of(state)
        if error or not code:
            result = "annule"
        else:
            try:
                self.instagram.complete(db, code, state)
                result = "ok"
            except InstagramError:
                result = "erreur"
        base = self.org_url(db, org_id) if self.org_url is not None else ""
        return RedirectResponse(f"{base.rstrip('/')}/?instagram={result}", status_code=303)

    def _reader(self, db: Session, appelant: Compte | None, ecole_id: int) -> None:
        rbac.require_membre(appelant, ecole_id)
        if not self.client.can_read(db, appelant, ecole_id):
            raise HTTPException(status_code=403, detail="Les actualités ne sont pas visibles")

    def _publisher(self, appelant: Compte | None, ecole_id: int) -> None:
        rbac.require_membre(appelant, ecole_id)
        if not can_publish(appelant):
            raise HTTPException(status_code=403, detail="Réservé aux personnes qui publient les actualités")

    def _item(self, db: Session, ecole_id: int, item_id: int) -> NewsItem:
        item = self.client.get(db, ecole_id, item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Actu introuvable")
        return item

    def feed(self, ecole_id: int, db: Session = Depends(get_db), appelant: Compte = Depends(rbac.compte_appelant)):
        """The news everybody sees; opening them clears « Nouveau »."""
        self._reader(db, appelant, ecole_id)
        me = appelant.id if appelant is not None else None
        seen = self.client.last_seen(db, me) if me is not None else None
        items = [_out(self.client, db, i, seen, me) for i in self.client.published(db, ecole_id)]
        if me is not None:
            self.client.mark_seen(db, me)
        return FeedOut(can_publish=can_publish(appelant), media_first=self.client.media_first(db, ecole_id), items=items)

    def workshop(self, ecole_id: int, db: Session = Depends(get_db), appelant: Compte = Depends(rbac.compte_appelant)):
        self._publisher(appelant, ecole_id)
        return [_out(self.client, db, i) for i in self.client.workshop(db, ecole_id)]

    def create(self, ecole_id: int, data: NewsIn, db: Session = Depends(get_db),
               appelant: Compte = Depends(rbac.compte_appelant)):
        self._publisher(appelant, ecole_id)
        return _out(self.client, db, self._save(db, ecole_id, appelant, None, data))

    def update(self, ecole_id: int, item_id: int, data: NewsIn, db: Session = Depends(get_db),
               appelant: Compte = Depends(rbac.compte_appelant)):
        self._publisher(appelant, ecole_id)
        item = self._item(db, ecole_id, item_id)
        return _out(self.client, db, self._save(db, ecole_id, appelant, item, data))

    def unpublish(self, ecole_id: int, item_id: int, db: Session = Depends(get_db),
                  appelant: Compte = Depends(rbac.compte_appelant)):
        self._publisher(appelant, ecole_id)
        return _out(self.client, db, self.client.unpublish(db, self._item(db, ecole_id, item_id)))

    def delete(self, ecole_id: int, item_id: int, db: Session = Depends(get_db),
               appelant: Compte = Depends(rbac.compte_appelant)):
        self._publisher(appelant, ecole_id)
        self.client.delete(db, self._item(db, ecole_id, item_id))

    def _save(self, db: Session, ecole_id: int, appelant: Compte | None, item: NewsItem | None, data: NewsIn):
        try:
            return self.client.save(db, ecole_id, appelant, item, **data.model_dump())
        except InvalidMedia as erreur:
            raise HTTPException(status_code=400, detail=str(erreur)) from erreur

    def upload_photo(self, ecole_id: int, fichier: UploadFile, appelant: Compte = Depends(rbac.compte_appelant)):
        self._publisher(appelant, ecole_id)
        try:
            return PhotoOut(photo=self.client.store_photo(ecole_id, fichier.file))
        except FileTooLarge as erreur:
            raise HTTPException(status_code=413, detail="Photo trop lourde (25 Mo au plus)") from erreur
        except InvalidMedia as erreur:
            raise HTTPException(status_code=400, detail=str(erreur)) from erreur

    def add_link(self, ecole_id: int, data: LinkIn, appelant: Compte = Depends(rbac.compte_appelant)):
        """A link for the carousel: its title and picture, read now (§3.3)."""
        self._publisher(appelant, ecole_id)
        try:
            title, photo = self.client.read_link(ecole_id, data.url)
        except LinkError as erreur:
            raise HTTPException(status_code=400, detail=str(erreur)) from erreur
        preview = None
        if photo:
            preview = "data:image/jpeg;base64," + base64.b64encode(self.client.thumbnail(ecole_id, photo).read_bytes()).decode()
        return LinkOut(link=data.url.strip(), title=title, photo=photo, preview=preview)

    def add_video(self, ecole_id: int, data: VideoIn, db: Session = Depends(get_db),
                  appelant: Compte = Depends(rbac.compte_appelant)):
        """« Publier » with a video: the upload (module Vidéos, by blocks)
        becomes a video, which the item then names."""
        self._publisher(appelant, ecole_id)
        if appelant is None:
            raise HTTPException(status_code=401, detail="Session requise")
        upload = self.client.videos.obtenir_televersement(db, data.upload_id)
        if upload is None or upload.ecole_id != ecole_id:
            raise HTTPException(status_code=404, detail="Envoi introuvable")
        return self.client.videos.finaliser(db, data.upload_id, nom="Actualité", uploaded_by=appelant.id)

    def photo(self, ecole_id: int, item_id: int, sha: str, db: Session = Depends(get_db),
              appelant: Compte = Depends(rbac.compte_appelant)):
        self._reader(db, appelant, ecole_id)
        item = self._item(db, ecole_id, item_id)
        if item.published_at is None and not can_publish(appelant):
            raise HTTPException(status_code=404, detail="Actu introuvable")
        chemin = self.client.photo_path(item, sha)
        if chemin is None or not chemin.exists():
            raise HTTPException(status_code=404, detail="Pas de photo")
        return FileResponse(chemin, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=31536000, immutable"})

    def _settings_out(self, db: Session, ecole_id: int, reader: bool) -> SettingsOut:
        return SettingsOut(
            open_on_news=reader and self.client.open_on_news(db, ecole_id), can_read=reader,
            media_first=self.client.media_first(db, ecole_id),
            visible_to_all=self.client.visible_to_all(db, ecole_id),
            has_news=reader and self.client.has_published(db, ecole_id),
        )

    def settings(self, ecole_id: int, db: Session = Depends(get_db), appelant: Compte = Depends(rbac.compte_appelant)):
        rbac.require_membre(appelant, ecole_id)
        return self._settings_out(db, ecole_id, self.client.can_read(db, appelant, ecole_id))

    def change_settings(self, ecole_id: int, data: SettingsIn, db: Session = Depends(get_db),
                        appelant: Compte = Depends(rbac.compte_appelant)):
        self._publisher(appelant, ecole_id)
        if data.open_on_news is not None:
            self.client.set_open_on_news(db, ecole_id, data.open_on_news)
        if data.media_first is not None:
            self.client.set_media_first(db, ecole_id, data.media_first)
        if data.visible_to_all is not None:
            self.client.set_visible_to_all(db, ecole_id, data.visible_to_all)
        return self._settings_out(db, ecole_id, True)
