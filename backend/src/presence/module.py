"""Déclaration du module Présence (spec/core.md §9 bis), propre à
Contretemps : séances, présences des élèves et heures des profs."""

from registry import Module

from .presence import Presence
from .receiver import PresenceReceiver


def mount(app, core) -> None:
    core.presence_client = Presence(cours=core.cours_client)
    PresenceReceiver(client=core.presence_client, app=app)


MODULE = Module(key="presence", label="Présence", mount=mount)
