"""Déclaration du sous-module Notes de frais pour Contretemps (spec/core.md
§9 bis, spec/modules/notes-de-frais.md) : le module `notes_frais` est relié
ici aux fiches, à la messagerie et au dossier Financier des Docs."""

import os
from pathlib import Path

from notes_frais import LecteurClaude, NotesDeFrais, NotesDeFraisReceiver, Ports, StockageEnveloppes
from registry import Module

from .adapter import (
    AnnuaireContretemps,
    ClasseurContretemps,
    MessagerContretemps,
    NotifieurContretemps,
    membre_appelant,
)

# Justificatifs : jamais servis en statique, seulement par les routes du
# module, après contrôle des droits.
DOSSIER_NOTES_FRAIS = Path(os.environ.get("NOTES_FRAIS_DIR", "./data/notes_frais"))


def mount(app, core) -> None:
    ressources = core.ressources_client
    core.notes_frais_client = NotesDeFrais(
        ports=Ports(
            annuaire=AnnuaireContretemps(),
            messager=MessagerContretemps(),
            notifieur=NotifieurContretemps(core.notifications_client),
            lecteur=LecteurClaude(
                noter_cout=lambda db, ecole_id, cout, detail: ressources.noter_ia(db, ecole_id, "lecture_ticket", cout, detail),
                plafond_atteint=ressources.plafond_assistant_atteint,
            ),
            # Justificatifs rangés dans Docs › Financier › Notes de frais.
            classeur=ClasseurContretemps(core.documents_client),
        ),
        stockage=StockageEnveloppes(DOSSIER_NOTES_FRAIS, 20 * 1024 * 1024),
    )
    NotesDeFraisReceiver(client=core.notes_frais_client, app=app, membre_courant=membre_appelant)


MODULE = Module(key="expense_notes", label="Notes de frais", mount=mount, requires=("documents",))
