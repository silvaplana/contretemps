"""Déclaration du module Chorégraphies (spec/core.md §9 bis), propre à
Contretemps : il s'appuie sur les cours et sur le module Vidéos."""

from registry import Module, guide_file

from .actions import actions
from .choregraphies import Choregraphies
from .receiver import ChoregraphiesReceiver


def mount(app, core) -> None:
    core.choregraphies_client = Choregraphies(cours=core.cours_client, videos=core.videos_client)
    ChoregraphiesReceiver(client=core.choregraphies_client, app=app)


MODULE = Module(
    key="choregraphies", label="Chorégraphies", mount=mount, requires=("videos",),
    actions=lambda core: actions(core.choregraphies_client),
    guide=guide_file(__file__),
)
