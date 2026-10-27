"""Déclaration du module HelloAsso (spec/core.md §9 bis,
spec/modules/helloasso.md). Éteint dans les écoles existantes (migration du
27 octobre 2026) : une école le coche quand elle encaisse sur HelloAsso."""

from registry import Module

from .connection import Connection
from .receiver import HelloAssoReceiver


def mount(app, core) -> None:
    core.helloasso_connection = Connection()
    HelloAssoReceiver(client=core.helloasso_connection, app=app)


MODULE = Module(key="helloasso", label="HelloAsso", mount=mount)
