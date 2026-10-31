"""Déclaration du module Messagerie instantanée (spec/core.md §9 bis)."""

from registry import Module, guide_file

from .actions import actions
from .connexions import Connexions
from .conversations import Conversations
from .frappe import Frappe
from .messages import Messages
from .receiver import MessagerieReceiver


def mount(app, core) -> None:
    # Fiches et cours (membres d'un groupe de cours), flux en direct
    # (core.evenements_client), notifications push d'un nouveau message, et
    # dossier des photos et fichiers choisi par l'appli.
    conversations = Conversations(comptes=core.comptes_client, cours=core.cours_client)
    core.messagerie_receiver = MessagerieReceiver(
        conversations=conversations,
        messages=Messages(conversations=conversations),
        evenements=core.evenements_client,
        connexions=Connexions(
            comptes=core.comptes_client, conversations=conversations, evenements=core.evenements_client
        ),
        frappe=Frappe(),
        notifications=core.notifications_client,
        attachments=core.message_attachments,
        app=app,
    )


MODULE = Module(
    key="messaging", label="Messagerie", mount=mount,
    actions=lambda core: actions(core.messagerie_receiver),
    guide=guide_file(__file__),
)
