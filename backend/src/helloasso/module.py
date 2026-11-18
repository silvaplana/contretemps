"""Déclaration du module HelloAsso (spec/core.md §9 bis,
spec/modules/helloasso.md). Éteint dans les écoles existantes (migration du
27 octobre 2026) : une école le coche quand elle encaisse sur HelloAsso."""

from registry import Module, guide_file

from . import members
from .campaign import Campaigns
from .connection import Connection
from .receiver import HelloAssoReceiver
from .sync import Sync


def add_member(eleves):
    """La fiche d'un inscrit : une fiche d'élève de l'appli (Contretemps),
    créée malgré le verrou (c'est la synchronisation qui l'apporte)."""
    def add(db, org_id, nom, prenom, email):
        return eleves.create(db, org_id, nom, prenom, email=email, external=True)[0]

    return add


def mount(app, core) -> None:
    # Saison imposée par une campagne : plus de fiche d'élève créée,
    # importée ou supprimée à la main (spec/modules/helloasso.md §7.1).
    core.eleves_client.locks.append(members.lock)
    core.helloasso_connection = Connection()
    core.helloasso_campaigns = Campaigns()
    core.helloasso_sync = Sync(add_member=add_member(core.eleves_client))
    core.helloasso_receiver = HelloAssoReceiver(
        client=core.helloasso_connection, app=app, campaigns=core.helloasso_campaigns, sync=core.helloasso_sync
    )


MODULE = Module(key="helloasso", label="HelloAsso", mount=mount, guide=guide_file(__file__))
