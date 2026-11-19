"""Déclaration des Drives du club (spec/core.md §3). Éteint par défaut :
allumé pour les écoles de nature « combat » (ASC) par la migration. Les
autres modules l'utilisent par `core.drives`."""

from registry import Module, guide_file

from .receiver import DrivesReceiver
from .service import Drives


def mount(app, core) -> None:
    core.drives = Drives()
    core.drives_receiver = DrivesReceiver(drives=core.drives, app=app)


MODULE = Module(
    key="drives", label="Drives du club", mount=mount,
    guide=guide_file(__file__), enabled_by_default=False,
)
