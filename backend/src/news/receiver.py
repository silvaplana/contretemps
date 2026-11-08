"""HTTP routes of the news module (spec/modules/actualites.md §8). Reading:
every member of the organization; writing: the right « 🔒 Publier les
actualités » (`news.publish`)."""

from __future__ import annotations

from datetime import date

from comptes import Compte, rbac, roles
from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from storage import FileTooLarge
from videos.schemas import VideoSortie

from db import get_db

from .models import NewsItem
from .instagram import InstagramError, InstagramRelay
from .news import InvalidMedia, News, on_top
from .schemas import (
    DocumentOut, FeedOut, InstagramIn, InstagramOut, NewsIn, NewsOut, PhotoOut, SettingsIn, SettingsOut, VideoIn,
)

PUBLISH = "news.publish"


def can_publish(appelant: Compte | None) -> bool:
    # `appelant=None`: rights switched off (tests, see tests/conftest.py).
    return appelant is None or roles.has_right(appelant, PUBLISH)


def _out(client: News, db: Session, item: NewsItem, seen=None, me: int | None = None) -> NewsOut:
    is_new = bool(seen is not None and item.published_at and item.published_at > seen and item.author_id != me)
    video = client.video(db, item)
    document = client.document(db, item)
    return NewsOut(
        id=item.id, level=item.level, body=item.body, on_top_until=item.on_top_until,
        on_top=on_top(item, date.today()), notify=item.notify, author_name=item.author_name,
        published_at=item.published_at, updated_at=item.updated_at, is_new=is_new,
        photo=item.photo_sha,
        video=VideoSortie.model_validate(video) if video else None,
        document=DocumentOut(id=document.id, name=document.name) if document else None,
    )


class NewsReceiver:
    def __init__(self, client: News, instagram: InstagramRelay, app: FastAPI) -> None:
        self.client = client
        self.instagram = instagram
        app.get("/ecoles/{ecole_id}/news", response_model=FeedOut)(self.feed)
        app.get("/ecoles/{ecole_id}/news/atelier", response_model=list[NewsOut])(self.workshop)
        app.post("/ecoles/{ecole_id}/news", response_model=NewsOut, status_code=201)(self.create)
        app.post("/ecoles/{ecole_id}/news/photos", response_model=PhotoOut, status_code=201)(self.upload_photo)
        app.post("/ecoles/{ecole_id}/news/videos", response_model=VideoSortie, status_code=201)(self.add_video)
        app.get("/ecoles/{ecole_id}/news/settings", response_model=SettingsOut)(self.settings)
        app.put("/ecoles/{ecole_id}/news/settings", response_model=SettingsOut)(self.change_settings)
        app.get("/ecoles/{ecole_id}/news/instagram", response_model=InstagramOut)(self.instagram_status)
        app.put("/ecoles/{ecole_id}/news/instagram", response_model=InstagramOut)(self.instagram_link)
        app.delete("/ecoles/{ecole_id}/news/instagram", response_model=InstagramOut)(self.instagram_unlink)
        app.put("/ecoles/{ecole_id}/news/{item_id}", response_model=NewsOut)(self.update)
        app.post("/ecoles/{ecole_id}/news/{item_id}/unpublish", response_model=NewsOut)(self.unpublish)
        app.delete("/ecoles/{ecole_id}/news/{item_id}", status_code=204)(self.delete)
        app.get("/ecoles/{ecole_id}/news/{item_id}/photo")(self.photo)

    @staticmethod
    def _instagram_out(link) -> InstagramOut:
        if link is None:
            return InstagramOut(linked=False)
        return InstagramOut(linked=True, username=link.username, last_sync_at=link.last_sync_at, last_error=link.last_error)

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
        return InstagramOut(linked=False)

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
        rbac.require_membre(appelant, ecole_id)
        me = appelant.id if appelant is not None else None
        seen = self.client.last_seen(db, me) if me is not None else None
        items = [_out(self.client, db, i, seen, me) for i in self.client.published(db, ecole_id)]
        if me is not None:
            self.client.mark_seen(db, me)
        return FeedOut(can_publish=can_publish(appelant), items=items)

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

    def photo(self, ecole_id: int, item_id: int, db: Session = Depends(get_db),
              appelant: Compte = Depends(rbac.compte_appelant)):
        rbac.require_membre(appelant, ecole_id)
        item = self._item(db, ecole_id, item_id)
        if item.published_at is None and not can_publish(appelant):
            raise HTTPException(status_code=404, detail="Actu introuvable")
        chemin = self.client.photo_path(item)
        if chemin is None or not chemin.exists():
            raise HTTPException(status_code=404, detail="Pas de photo")
        return FileResponse(chemin, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=31536000, immutable"})

    def settings(self, ecole_id: int, db: Session = Depends(get_db), appelant: Compte = Depends(rbac.compte_appelant)):
        rbac.require_membre(appelant, ecole_id)
        return SettingsOut(open_on_news=self.client.open_on_news(db, ecole_id))

    def change_settings(self, ecole_id: int, data: SettingsIn, db: Session = Depends(get_db),
                        appelant: Compte = Depends(rbac.compte_appelant)):
        self._publisher(appelant, ecole_id)
        self.client.set_open_on_news(db, ecole_id, data.open_on_news)
        return SettingsOut(open_on_news=data.open_on_news)
