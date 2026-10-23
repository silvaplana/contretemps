"""Déclaration du module Assistant IA (spec/core.md §9 bis). Ses actions
sont celles que les autres modules lui ouvrent (assistant-ia.md §3), remises
par l'appli dans app/main.py."""

from registry import Module

from .assistant import Assistant
from .modifications import Modifications
from .receiver import AssistantReceiver


def mount(app, core) -> None:
    ressources = core.ressources_client
    assistant_client = Assistant(
        documents=core.documents_client,
        noter_cout=lambda db, ecole_id, cout, detail: ressources.noter_ia(db, ecole_id, "chat_documents", cout, detail),
        cout_saison=lambda db, ecole_id: ressources.cout_categorie(db, ecole_id, "chat_documents"),
    )
    assistant_client.plafond_atteint = ressources.plafond_assistant_atteint
    assistant_client.modifications = Modifications(
        eleves=core.eleves_client, comptes=core.comptes_client, cours=core.cours_client,
        presence=core.presence_client, choregraphies=core.choregraphies_client,
    )
    core.assistant_client = assistant_client
    AssistantReceiver(client=assistant_client, app=app, current_member=core.membre_appelant)


MODULE = Module(
    key="assistant", label="Assistant", mount=mount, requires=("documents", "presence", "choregraphies")
)
