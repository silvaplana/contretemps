"""Assistant actions of the Publications module (spec/modules/actualites.md
§9, §12.9): publish a post in a blog and delete one. Same right as the
screen: the blog's « Publier dans <blog> »."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from assistant.actions import Action
from assistant.modifications import Ligne, Refus
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .models import Blog
from .publications import InvalidMedia, Publications, can_publish, normalized

LABELS = {"important": "importante", "normal": "", "brief": "brève"}


class PublishNews(BaseModel):
    body: str = Field(min_length=1, description="Texte de la publication, tel que l'a dicté la personne.")
    blog: str | None = Field(None, description="Nom de l'onglet où publier (ex. « Actus », « Techniques ») ; par défaut le premier.")
    level: Literal["important", "normal", "brief"] = Field(
        "normal", description="Onglet avec niveaux seulement. important : en haut, en rouge ; normal ; brief : une ligne.")
    on_top_until: date | None = Field(None, description="Important seulement : en haut jusqu'à ce jour (par défaut dans 7 jours).")
    notify: bool | None = Field(None, description="Envoyer une notification ; par défaut oui pour important, non sinon.")
    title: str | None = Field(None, description="Onglet avec catégories : nom de la publication (obligatoire).")
    category: str | None = Field(None, description="Onglet avec catégories : sa catégorie (obligatoire), existante de préférence.")
    subcategory: str | None = Field(None, description="Onglet avec catégories : sa sous-catégorie, facultative.")


class DeleteNews(BaseModel):
    news_id: int = Field(description="Numéro de la publication.")
    blog: str | None = Field(None, description="Nom de l'onglet ; par défaut le premier.")


def _blog(client: Publications, db: Session, org_id: int, name: str | None) -> Blog:
    blogs = client.blogs(db, org_id)
    if not name:
        return blogs[0]
    for blog in blogs:
        if normalized(blog.name) == normalized(name):
            return blog
    raise Refus(f"pas d'onglet « {name} » ; onglets : {', '.join(b.name for b in blogs)}")


def _check(compte, blog: Blog) -> None:
    if not can_publish(compte, blog):
        raise Refus(f"réservé aux personnes qui ont le droit « Publier dans {blog.name} »")


def actions(client: Publications) -> list[Action]:
    def prepare_publish(db: Session, compte, org_id: int, p: PublishNews) -> Ligne:
        blog = _blog(client, db, org_id, p.blog)
        _check(compte, blog)
        level = p.level if blog.with_levels else "normal"
        if blog.with_categories and not ((p.title or "").strip() and (p.category or "").strip()):
            raise Refus(f"dans {blog.name}, il faut un nom et une catégorie")
        notify = p.notify if p.notify is not None else level == "important"
        until = (p.on_top_until or date.today() + timedelta(days=7)) if level == "important" else None
        apercu = p.title or (p.body if len(p.body) <= 60 else p.body[:59] + "…")
        nature = f" {LABELS[level]}" if LABELS[level] else ""
        blog_id = blog.id

        def publish(db: Session) -> None:
            try:
                client.save(db, db.get(Blog, blog_id), compte, None, level=level, body=p.body, on_top_until=until,
                            notify=notify, publish=True, title=p.title, category=p.category,
                            subcategory=p.subcategory)
            except InvalidMedia as erreur:
                raise Refus(str(erreur)) from erreur

        return Ligne(f"Publier{nature} dans {blog.name} « {apercu} »" + (", avec notification" if notify else ""), publish)

    def prepare_delete(db: Session, compte, org_id: int, p: DeleteNews) -> Ligne:
        blog = _blog(client, db, org_id, p.blog)
        _check(compte, blog)
        post = client.get(db, blog, p.news_id)
        if post is None:
            raise Refus(f"publication introuvable dans {blog.name}")
        post_id, blog_id = post.id, blog.id
        apercu = post.title or (post.body if len(post.body) <= 60 else post.body[:59] + "…") or "sans texte"
        return Ligne(f"Supprimer de {blog.name} « {apercu} »",
                     lambda db: client.delete(db, client.get(db, db.get(Blog, blog_id), post_id)))

    # Names kept from the module's first name (`news`).
    return [
        Action("publish_news", "Publications", "Publie dans un onglet de publications (Actus, Techniques…).",
               PublishNews, prepare_publish, admin_only=False),
        Action("delete_news", "Publications", "Supprime une publication d'un onglet (Actus, Techniques…).",
               DeleteNews, prepare_delete, admin_only=False),
    ]
