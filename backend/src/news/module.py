"""Déclaration du module Actualités (spec/core.md §9 bis,
spec/modules/actualites.md) : l'onglet Actus et son droit « 🔒 Publier les
actualités », coché comme « Accès au Financier » dans Admin > École >
Administrateurs."""

from db import SessionLocal
from registry import Module, Right, guide_file

from .actions import actions
from .instagram import InstagramRelay
from .news import News
from .receiver import PUBLISH, READ, NewsReceiver
from .storage import news_storage


def mount(app, core) -> None:
    core.news_client = News(
        notifications=core.notifications_client, storage=news_storage(), videos=core.videos_client,
        session_factory=SessionLocal,
    )
    core.news_instagram = InstagramRelay(core.news_client)
    NewsReceiver(client=core.news_client, instagram=core.news_instagram, app=app)


MODULE = Module(
    key="news", label="Actualités", mount=mount, requires=("videos",),
    rights=(Right(PUBLISH, "Publier les actualités"), Right(READ, "Voir les actualités")),
    actions=lambda core: actions(core.news_client),
    guide=guide_file(__file__),
)
