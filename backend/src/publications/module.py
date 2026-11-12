"""Déclaration du module Publications (spec/core.md §9 bis,
spec/modules/actualites.md §12) : un onglet par blog de l'organisation
(Actus, Techniques…) et, par blog, son droit « 🔒 Publier dans <blog> »,
coché comme « Accès au Financier » dans Admin > École > Administrateurs."""

from db import SessionLocal
from registry import Module, guide_file

from .actions import actions
from .instagram import InstagramApp, InstagramRelay
from .publications import Publications, org_rights
from .receiver import PublicationsReceiver
from .storage import publications_storage


def mount(app, core) -> None:
    core.publications_client = Publications(
        notifications=core.notifications_client, storage=publications_storage(), videos=core.videos_client,
        session_factory=SessionLocal,
    )
    core.publications_instagram = InstagramRelay(core.publications_client, app=InstagramApp.from_env())
    PublicationsReceiver(client=core.publications_client, instagram=core.publications_instagram, app=app,
                         org_url=_org_url)


def _org_url(db, org_id):
    """The address of the school's app (its subdomain), or the general one."""
    from auth.mails import MailsAcces
    from ecoles.models import Ecole

    ecole = db.get(Ecole, org_id) if org_id is not None else None
    return MailsAcces().appli(ecole.sous_domaine if ecole is not None else None)


MODULE = Module(
    key="publications", label="Publications", mount=mount, requires=("videos",),
    org_rights=org_rights,
    actions=lambda core: actions(core.publications_client),
    guide=guide_file(__file__),
)
