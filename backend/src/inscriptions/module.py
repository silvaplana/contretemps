"""Déclaration du module Inscription en ligne (spec/core.md §9 bis,
spec/SPEC-inscription.md) : routes PUBLIQUES, atteignables sans compte."""

from registry import Module

from .fiches import FichesPapier
from .helloasso import HelloAsso
from .inscriptions import Inscriptions
from .receiver import InscriptionsReceiver


def mount(app, core) -> None:
    ressources = core.ressources_client
    core.inscriptions_client = Inscriptions(cours=core.cours_client, helloasso=HelloAsso())
    core.inscriptions_receiver = InscriptionsReceiver(
        client=core.inscriptions_client,
        app=app,
        fiches=FichesPapier(
            cours=core.cours_client,
            eleves=core.eleves_client,
            noter_cout=lambda db, ecole_id, cout, detail: ressources.noter_ia(db, ecole_id, "lecture_fiche", cout, detail),
        ),
    )


# Tarifs et formulaire par saison (spec/modules/saisons.md §2).
MODULE = Module(key="registration", label="Inscription en ligne", mount=mount, requires=("seasons",))
