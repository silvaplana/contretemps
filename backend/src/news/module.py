"""Déclaration du module Actualités (spec/core.md §9 bis,
spec/modules/actualites.md) : l'onglet Actus et son droit « 🔒 Publier les
actualités », coché comme « Accès au Financier » dans Admin > École >
Administrateurs."""

from db import SessionLocal
from registry import Module, Right, guide_file

from .actions import actions
from .news import News
from .receiver import PUBLISH, NewsReceiver


def mount(app, core) -> None:
    core.news_client = News(notifications=core.notifications_client, session_factory=SessionLocal)
    NewsReceiver(client=core.news_client, app=app)


MODULE = Module(
    key="news", label="Actualités", mount=mount,
    rights=(Right(PUBLISH, "Publier les actualités"),),
    actions=lambda core: actions(core.news_client),
    guide=guide_file(__file__),
)
