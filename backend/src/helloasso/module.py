"""Déclaration du module HelloAsso (spec/core.md §9 bis,
spec/modules/helloasso.md). Éteint par défaut (Seb, 18 novembre 2026) : une
école le coche quand elle encaisse sur HelloAsso."""

from registry import Module, guide_file

from . import members, money, payment
from .campaign import Campaigns
from .connection import Connection
from .receiver import HelloAssoReceiver
from .stats import Sources, StatsReceiver
from .sync import Sync
from .verification import Checker, ChecksReceiver


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
    # Prévisionnel du Financier (financier.md §6.4) : l'argent HelloAsso à venir.
    core.helloasso_money = money.to_come
    core.helloasso_campaigns = Campaigns()
    core.helloasso_sync = Sync(add_member=add_member(core.eleves_client))
    core.helloasso_receiver = HelloAssoReceiver(
        client=core.helloasso_connection, app=app, campaigns=core.helloasso_campaigns, sync=core.helloasso_sync
    )
    # Mail à un adhérent (spec §7.6) : le service email du core.
    core.helloasso_receiver.send_mail = getattr(core, "mail_ecole", None)
    # Vérification des dossiers et « Nouvel adhérent » (spec §7.5), éteints
    # par défaut : réglages de la connexion.
    notifications = getattr(core, "notifications_client", None)
    core.helloasso_checker = Checker(
        send_mail=core.helloasso_receiver.send_mail,
        push=notifications.envoyer_a_compte if notifications else None,
        eur_per_usd=getattr(core, "eur_per_usd", lambda: 0.9),
    )
    core.helloasso_sync.on_new.append(core.helloasso_checker.on_new)
    ChecksReceiver(app, core.helloasso_checker, core.helloasso_receiver._registration)
    # Statistiques de la saison (spec §7.8) : les comptes et les licences
    # viennent d'autres modules, branchés par l'appli (helloasso_contretemps).
    core.helloasso_stats = Sources()
    StatsReceiver(app, core.helloasso_stats)


MODULE = Module(
    key="helloasso", label="HelloAsso", mount=mount, guide=guide_file(__file__), enabled_by_default=False
)
