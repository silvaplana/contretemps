"""Déclaration du sous-module Importation automatique de pièces du Financier
(spec/modules/import-auto-pieces.md). Éteint par défaut : allumé pour les
écoles de nature « combat » (ASC) par la migration. Contretemps ne change pas."""

import logging
import threading
import time

from registry import Module, guide_file

from .receiver import AutoImportReceiver
from .service import AutoImport

logger = logging.getLogger(__name__)


def _places(core):
    """Ce qu'on peut choisir comme source ou destination dans l'école."""

    def places(db, org_id: int) -> dict:
        from saisons.models import Saison
        from saisons.portee import toutes_saisons
        from sqlalchemy import select

        with toutes_saisons(db):
            saisons = list(db.scalars(select(Saison).where(Saison.ecole_id == org_id).order_by(Saison.date_debut.desc())))
        drives = getattr(core, "drives", None)
        mail = getattr(core, "mail_connection", None)
        return {
            "org_id": org_id,
            "seasons": [{"id": s.id, "name": s.nom} for s in saisons],
            "drives": [{"id": d.id, "name": d.name, "provider": d.provider} for d in drives.accounts(db, org_id)] if drives else [],
            "mail_boxes": [{"id": b.id, "name": b.name} for b in mail.accounts(db, org_id)] if mail else [],
        }

    return places


def _who(db, org_id: int, address: str) -> str | None:
    """La nature que donne un expéditeur de l'école (§4.1) : un prof,
    Honoraires ; un autre adhérent, Note de frais ; inconnu, None."""
    from comptes import roles
    from comptes.models import Compte, EmailCompte
    from sqlalchemy import select

    compte = db.scalar(select(Compte).join(EmailCompte, EmailCompte.compte_id == Compte.id).where(
        Compte.ecole_id == org_id, EmailCompte.email == address.strip().lower()).limit(1))
    if compte is None:
        return None
    return "honoraires" if roles.is_prof(compte) else "frais"


def _reader(notes):
    """La pièce jointe montre-t-elle un montant ou une date (lecteur des
    factures, §4.1) ? Sans lecteur : non."""

    def check(db, rule, content: bytes, mime: str, name: str) -> bool:
        from notes_frais.service import LectureImpossible

        if not notes.lecture_disponible:
            return False
        try:
            lu = notes.lire_ticket(db, AutoImport._membre(rule), content, mime, name)
        except LectureImpossible:
            return False
        return bool(lu.get("montant_centimes") or lu.get("date"))

    return check


def _helloasso_payments(db, org_id: int, season_id: int | None):
    """Les paiements versés de la copie HelloAsso (§4.2) : payés en ligne,
    versés (`CashedOut`), avec leur jour de versement. Un paiement remboursé
    après avoir été versé compte dans son versement, et son remboursement
    (en moins, au jour du remboursement) dans le versement suivant."""
    from datetime import date

    from helloasso.contact import PAID, REFUNDED
    from helloasso.models import HelloAssoRegistration
    from helloasso.money import CASHED_OUT, ONLINE_MEANS
    from sqlalchemy import select

    from dataclasses import replace

    from .helloasso_source import Payment

    query = select(HelloAssoRegistration).where(HelloAssoRegistration.org_id == org_id)
    if season_id is not None:
        query = query.where(HelloAssoRegistration.season_id == season_id)
    payments = []
    for r in db.scalars(query.order_by(HelloAssoRegistration.id)):
        for p in r.payments or []:
            state = p.get("state")
            if state not in PAID + REFUNDED or p.get("means") not in ONLINE_MEANS or p.get("cash_out_state") != CASHED_OUT:
                continue
            try:
                day = date.fromisoformat((p.get("cash_out_date") or "")[:10])
            except ValueError:
                continue
            paid = Payment(
                name=f"{r.first_name} {r.last_name}".strip(), formula=r.tier_name or "", amount=p.get("amount") or 0,
                installment=p.get("installment"), paid_on=p.get("date") or "", cash_out_date=day,
            )
            payments.append(paid)
            if state in REFUNDED and p.get("refunded_on"):
                payments.append(replace(paid, amount=-paid.amount, paid_on=p["refunded_on"], cash_out_date=None))
    return payments


def _helloasso_formulas(db, org_id: int, season_id: int | None) -> list[str]:
    from helloasso.models import HelloAssoRegistration
    from sqlalchemy import select

    query = select(HelloAssoRegistration.tier_name).where(HelloAssoRegistration.org_id == org_id).distinct()
    if season_id is not None:
        query = query.where(HelloAssoRegistration.season_id == season_id)
    return sorted({f or "" for f in db.scalars(query)})


LICENCES = ("4671", "Licences FFST à reverser")


def _licence_account(db, org_id: int, add: bool = False) -> dict | None:
    """Le compte des licences à reverser (§4.2) : un compte de tiers 467…
    du plan dont le libellé parle de licences ; `add` : l'ajouter (4671, ou
    un numéro libre si 4671 sert déjà) ou le réactiver. Sa catégorie de
    pièce est à part, jamais proposée ailleurs (comme 431 de la paie)."""
    from finances.models import THIRD_PARTY, FinChartAccount
    from notes_frais.models import CategorieFrais
    from sqlalchemy import select

    accounts = list(db.scalars(select(FinChartAccount).where(FinChartAccount.org_id == org_id)))
    found = sorted((a for a in accounts if a.number.startswith("467") and "licence" in a.label.lower()),
                   key=lambda a: (not a.active, a.number))
    account = found[0] if found else None
    if account is None or not account.active:
        if not add:
            return None
        if account is None:
            used = {a.number for a in accounts}
            number = next(n for n in (LICENCES[0], "4675", "4678", "46710", "46790", "46799") if n not in used)
            account = FinChartAccount(org_id=org_id, number=number, label=LICENCES[1], nature=THIRD_PARTY, keywords=[])
            db.add(account)
        account.active = True
        db.flush()
    categorie = db.scalar(select(CategorieFrais).where(CategorieFrais.org_id == org_id, CategorieFrais.code == account.number))
    if categorie is None:
        categorie = CategorieFrais(org_id=org_id, code=account.number, libelle=account.label[:60], ordre=999, active=False)
        db.add(categorie)
    db.commit()
    return {"id": categorie.id, "code": account.number, "libelle": account.label}


def mount(app, core) -> None:
    from notes_frais_contretemps.adapter import membre_appelant

    from .mail_source import mail_source

    sources = {}
    if getattr(core, "mail_connection", None) is not None:
        sources["mail"] = mail_source(core.mail_connection, _who, _reader(core.notes_frais_client))
    from .helloasso_source import helloasso_source

    sources["helloasso"] = helloasso_source(_helloasso_payments, _licence_account)
    core.auto_import = AutoImport(
        notes=core.notes_frais_client, documents=core.documents_client, drives=getattr(core, "drives", None),
        sources=sources,
    )
    AutoImportReceiver(client=core.auto_import, app=app, membre_courant=membre_appelant, places=_places(core),
                       formulas=_helloasso_formulas, licence_account=_licence_account)


def start_loop(core, every_seconds: int = 300) -> None:
    """Regarde les imports dont l'heure est venue, toutes les 5 minutes.
    Lancé par `app.main.main()` seulement (jamais sous pytest)."""
    from db import SessionLocal

    def boucle():
        while True:
            try:
                with SessionLocal() as db:
                    core.auto_import.run_due(db)
            except Exception:
                logger.exception("Importation automatique de pièces : passage impossible")
            time.sleep(every_seconds)

    threading.Thread(target=boucle, name="auto-import", daemon=True).start()


MODULE = Module(
    key="auto_import", label="Importation automatique de pièces", mount=mount, requires=("expense_notes",),
    guide=guide_file(__file__), enabled_by_default=False,
)
