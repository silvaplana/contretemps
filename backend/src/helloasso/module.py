"""Déclaration du module HelloAsso (spec/core.md §9 bis,
spec/modules/helloasso.md). Éteint par défaut (Seb, 18 novembre 2026) : une
école le coche quand elle encaisse sur HelloAsso."""

from registry import Module, guide_file

from . import members, payment
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
    # « L'appli fait tout, HelloAsso encaisse » : le paiement en ligne de
    # l'inscription prend les clés de l'école (helloasso.md §8.2).
    registration = getattr(core, "inscriptions_client", None)
    if registration is not None:
        registration.helloasso.school_keys.append(payment.school_keys)
    core.helloasso_connection = Connection()
    core.helloasso_campaigns = Campaigns()
    core.helloasso_sync = Sync(add_member=add_member(core.eleves_client))
    core.helloasso_receiver = HelloAssoReceiver(
        client=core.helloasso_connection, app=app, campaigns=core.helloasso_campaigns, sync=core.helloasso_sync
    )
    # Mail à un adhérent (spec §7.6) : le service email du core.
    core.helloasso_receiver.send_mail = getattr(core, "mail_ecole", None)


MODULE = Module(
    key="helloasso", label="HelloAsso", mount=mount, guide=guide_file(__file__), enabled_by_default=False
)
