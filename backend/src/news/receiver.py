"""HTTP routes of the news module (spec/modules/actualites.md §8). Reading:
every member of the organization; writing: the right « 🔒 Publier les
actualités » (`news.publish`)."""

from __future__ import annotations

from datetime import date

from comptes import Compte, rbac, roles
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from db import get_db

from .models import NewsItem
from .news import News, on_top
from .schemas import FeedOut, NewsIn, NewsOut, SettingsIn, SettingsOut

PUBLISH = "news.publish"


def can_publish(appelant: Compte | None) -> bool:
    # `appelant=None`: rights switched off (tests, see tests/conftest.py).
    return appelant is None or roles.has_right(appelant, PUBLISH)


def _out(item: NewsItem, seen=None, me: int | None = None) -> NewsOut:
    is_new = bool(seen is not None and item.published_at and item.published_at > seen and item.author_id != me)
    return NewsOut(
        id=item.id, level=item.level, body=item.body, on_top_until=item.on_top_until,
        on_top=on_top(item, date.today()), notify=item.notify, author_name=item.author_name,
        published_at=item.published_at, updated_at=item.updated_at, is_new=is_new,
    )


class NewsReceiver:
    def __init__(self, client: News, app: FastAPI) -> None:
        self.client = client
        app.get("/ecoles/{ecole_id}/news", response_model=FeedOut)(self.feed)
        app.get("/ecoles/{ecole_id}/news/atelier", response_model=list[NewsOut])(self.workshop)
        app.post("/ecoles/{ecole_id}/news", response_model=NewsOut, status_code=201)(self.create)
        app.get("/ecoles/{ecole_id}/news/settings", response_model=SettingsOut)(self.settings)
        app.put("/ecoles/{ecole_id}/news/settings", response_model=SettingsOut)(self.change_settings)
        app.put("/ecoles/{ecole_id}/news/{item_id}", response_model=NewsOut)(self.update)
        app.post("/ecoles/{ecole_id}/news/{item_id}/unpublish", response_model=NewsOut)(self.unpublish)
        app.delete("/ecoles/{ecole_id}/news/{item_id}", status_code=204)(self.delete)

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
        items = [_out(i, seen, me) for i in self.client.published(db, ecole_id)]
        if me is not None:
            self.client.mark_seen(db, me)
        return FeedOut(can_publish=can_publish(appelant), items=items)

    def workshop(self, ecole_id: int, db: Session = Depends(get_db), appelant: Compte = Depends(rbac.compte_appelant)):
        self._publisher(appelant, ecole_id)
        return [_out(i) for i in self.client.workshop(db, ecole_id)]

    def create(self, ecole_id: int, data: NewsIn, db: Session = Depends(get_db),
               appelant: Compte = Depends(rbac.compte_appelant)):
        self._publisher(appelant, ecole_id)
        return _out(self.client.save(db, ecole_id, appelant, None, **data.model_dump()))

    def update(self, ecole_id: int, item_id: int, data: NewsIn, db: Session = Depends(get_db),
               appelant: Compte = Depends(rbac.compte_appelant)):
        self._publisher(appelant, ecole_id)
        item = self._item(db, ecole_id, item_id)
        return _out(self.client.save(db, ecole_id, appelant, item, **data.model_dump()))

    def unpublish(self, ecole_id: int, item_id: int, db: Session = Depends(get_db),
                  appelant: Compte = Depends(rbac.compte_appelant)):
        self._publisher(appelant, ecole_id)
        return _out(self.client.unpublish(db, self._item(db, ecole_id, item_id)))

    def delete(self, ecole_id: int, item_id: int, db: Session = Depends(get_db),
               appelant: Compte = Depends(rbac.compte_appelant)):
        self._publisher(appelant, ecole_id)
        self.client.delete(db, self._item(db, ecole_id, item_id))

    def settings(self, ecole_id: int, db: Session = Depends(get_db), appelant: Compte = Depends(rbac.compte_appelant)):
        rbac.require_membre(appelant, ecole_id)
        return SettingsOut(open_on_news=self.client.open_on_news(db, ecole_id))

    def change_settings(self, ecole_id: int, data: SettingsIn, db: Session = Depends(get_db),
                        appelant: Compte = Depends(rbac.compte_appelant)):
        self._publisher(appelant, ecole_id)
        self.client.set_open_on_news(db, ecole_id, data.open_on_news)
        return SettingsOut(open_on_news=data.open_on_news)
