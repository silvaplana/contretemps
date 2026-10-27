"""Déclaration du module Sparring pour Contretemps (spec/core.md §9 bis,
spec/modules/video-combats.md) : le module générique `session_clips`, relié
ici aux fiches de Contretemps. Éteint dans les écoles existantes (migration
du 27 octobre 2026) : on le met au point pour un club de combat."""

from registry import Module
from session_clips import SessionClips, SessionClipsReceiver

from .adapter import AnnuaireSparring, membre_appelant


def mount(app, core) -> None:
    core.session_clips_client = SessionClips(videos=core.videos_client, directory=AnnuaireSparring())
    SessionClipsReceiver(client=core.session_clips_client, app=app, current_member=membre_appelant)


MODULE = Module(key="session_clips", label="Sparring", mount=mount, requires=("videos",))
