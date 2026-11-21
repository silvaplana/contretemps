"""Déclaration du sous-module Mail de la Messagerie (spec/core.md §9 bis,
spec/modules/mail.md). Éteint par défaut : une école le coche dans
Fonctionnalités."""

from registry import Module, Right, guide_file

from .actions import actions
from .connection import Connection
from .receiver import RIGHT, MailReceiver


def mount(app, core) -> None:
    core.mail_connection = Connection()
    core.mail_receiver = MailReceiver(connection=core.mail_connection, app=app)


MODULE = Module(
    key="mail", label="Mail", mount=mount, requires=("messaging",),
    rights=(Right(RIGHT, "Boîte mail du club"),),
    guide=guide_file(__file__), enabled_by_default=False,
    actions=lambda core: actions(core.mail_receiver),
)
