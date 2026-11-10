"""Assistant actions of the news module (spec/modules/actualites.md §9):
publish a news item and delete one. Same right as the screen."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from assistant.actions import Action
from assistant.modifications import Ligne, Refus
from comptes import roles
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .news import News
from .receiver import PUBLISH

LABELS = {"important": "importante", "normal": "", "brief": "brève"}


class PublishNews(BaseModel):
    body: str = Field(min_length=1, description="Texte de l'actu, tel que l'a dicté la personne.")
    level: Literal["important", "normal", "brief"] = Field(
        "normal", description="important : en haut, en rouge ; normal ; brief : une ligne.")
    on_top_until: date | None = Field(None, description="Important seulement : en haut jusqu'à ce jour (par défaut dans 7 jours).")
    notify: bool | None = Field(None, description="Envoyer une notification ; par défaut oui pour important, non sinon.")


class DeleteNews(BaseModel):
    news_id: int = Field(description="Numéro de l'actu.")


def _check(compte) -> None:
    if not roles.has_right(compte, PUBLISH):
        raise Refus("réservé aux personnes qui ont le droit « Publier les actualités »")


def actions(client: News) -> list[Action]:
    def prepare_publish(db: Session, compte, org_id: int, p: PublishNews) -> Ligne:
        _check(compte)
        notify = p.notify if p.notify is not None else p.level == "important"
        until = (p.on_top_until or date.today() + timedelta(days=7)) if p.level == "important" else None
        apercu = p.body if len(p.body) <= 60 else p.body[:59] + "…"
        nature = f" {LABELS[p.level]}" if LABELS[p.level] else ""

        def publish(db: Session) -> None:
            client.save(db, org_id, compte, None, level=p.level, body=p.body,
                        on_top_until=until, notify=notify, publish=True)

        return Ligne(f"Publier l'actu{nature} « {apercu} »" + (", avec notification" if notify else ""), publish)

    def prepare_delete(db: Session, compte, org_id: int, p: DeleteNews) -> Ligne:
        _check(compte)
        item = client.get(db, org_id, p.news_id)
        if item is None:
            raise Refus("actu introuvable dans cette école")
        item_id = item.id
        apercu = (item.body if len(item.body) <= 60 else item.body[:59] + "…") or "sans texte"
        return Ligne(f"Supprimer l'actu « {apercu} »", lambda db: client.delete(db, client.get(db, org_id, item_id)))

    return [
        Action("publish_news", "Actualités", "Publie une actu dans l'onglet Actus.", PublishNews, prepare_publish,
               admin_only=False),
        Action("delete_news", "Actualités", "Supprime une actu de l'onglet Actus.", DeleteNews, prepare_delete,
               admin_only=False),
    ]
