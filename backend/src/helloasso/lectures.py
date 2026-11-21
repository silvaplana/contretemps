"""HelloAsso opened to the assistant, in reading (Seb, 20 November 2026: « il
faudra ouvrir sur la connexion à HelloAsso aussi »): the season's campaign,
the members with their status, « À encaisser » and the season's statistics.
Each reading calls the screen's route (same rights, same school, same
season), for the season shown or another one named.

Never read here: the keys, and the answers and files of the HelloAsso form
(the medical certificate, health questions). The connection itself (keys,
connect, disconnect) has no tool: it stays with the person.
"""

from __future__ import annotations

import json
from contextlib import nullcontext

from assistant.actions import Action
from assistant.modifications import Refus
from comptes import Compte, rbac, roles
from pydantic import BaseModel, Field
from saisons import Saison, saison_courante_id
from saisons.portee import dans_saison, saison_demandee
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import contact
from . import members as imposed_members
from .members import FAILED_PAYMENTS
from .receiver import HelloAssoReceiver
from .stats import PAID, REFUNDED, Sources, statistics
from .sync import is_cancelled

LIMIT_MAX = 300
SEASON = Field(default=None, description="Nom de la saison, ou null pour la saison affichée.")
MODES = {"master": "HelloAsso fait tout", "payment": "L'appli fait tout, HelloAsso encaisse", "none": "Sans HelloAsso"}


def _json(data) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str)


def _euros(cents) -> float:
    return (cents or 0) / 100


def season(db: Session, org_id: int, name: str | None) -> Saison:
    """The season named, or the one shown (as the screens)."""
    if name is None:
        season_id = saison_demandee() or saison_courante_id(db, org_id)
        found = db.get(Saison, season_id) if season_id else None
        if found is None or found.ecole_id != org_id:
            raise Refus("aucune saison")
        return found
    seasons = db.scalars(select(Saison).where(Saison.ecole_id == org_id).order_by(Saison.date_debut)).all()
    wanted = " ".join(name.split()).casefold()
    found = [s for s in seasons if s.nom.casefold() == wanted] or [s for s in seasons if wanted in s.nom.casefold()]
    if len(found) != 1:
        raise Refus(f"saison « {name} » " + ("introuvable" if not found else "ambiguë") + ". Saisons : "
                    + ", ".join(s.nom for s in seasons))
    return found[0]


def in_season(db: Session, org_id: int, found: Saison):
    """The block sees `found` as if the screen showed it."""
    shown = saison_demandee() or saison_courante_id(db, org_id)
    return nullcontext() if found.id == shown else dans_saison(found.id)


def payment_status(r) -> str:
    """payé, à encaisser (instalments to come), impayé (a payment refused or
    failed) or résilié."""
    if is_cancelled(r.state):
        return "résilié"
    states = [p.get("state") for p in r.payments or []]
    if any(s in FAILED_PAYMENTS for s in states):
        return "impayé"
    if any(s not in PAID | REFUNDED for s in states):
        return "à encaisser"
    return "payé"


class Campaign(BaseModel):
    season: str | None = SEASON
    refresh_list: bool = Field(default=False, description="« Relire la liste » : redemander à HelloAsso la liste des campagnes (sinon gardée 10 minutes).")


class Members(BaseModel):
    season: str | None = SEASON
    member_id: int | None = Field(default=None, description="Numéro de la fiche d'un adhérent pour sa fiche HelloAsso (paiements, messages envoyés, vérification), ou null pour le tableau.")
    text: str | None = Field(default=None, description="Bout de nom, prénom ou email, ou null.")
    status: str | None = Field(default=None, description="payé, à encaisser, impayé, résilié, ou « à vérifier » (dossier pas OK), ou null pour tous.")
    limit: int = Field(default=100, ge=1, le=LIMIT_MAX, description="Nombre d'adhérents au plus.")


class SeasonOnly(BaseModel):
    season: str | None = SEASON


def lectures(receiver: HelloAssoReceiver, sources: Sources) -> list[Action]:
    def read_campaign(db: Session, compte, org_id: int, p: Campaign) -> str:
        found = season(db, org_id, p.season)
        with in_season(db, org_id, found):
            mode = receiver.saison(org_id, db=db, appelant=compte)
            if not mode.connected:
                return _json({"connected": False, "season": found.nom})
            campaign = receiver.campagne(org_id, relire=p.refresh_list, db=db, appelant=compte)
        return _json({
            "connected": True,
            "season": found.nom,
            "current": mode.current,
            "mode": MODES.get(mode.mode, mode.mode),
            "campaign": campaign.form.model_dump() if campaign.form else None,
            "syncedAt": campaign.synced_at,
            "canChange": campaign.can_change,
            # Seen only by who may change it, as on screen.
            "campaigns": [f.model_dump() for f in campaign.forms] if campaign.can_change else None,
            "error": campaign.error,
        })

    def read_members(db: Session, compte, org_id: int, p: Members) -> str:
        found = season(db, org_id, p.season)
        with in_season(db, org_id, found):
            if p.member_id is not None:
                registration = receiver._registration(db, org_id, p.member_id, compte)
                card = imposed_members.card(db, registration)
                # The form's answers and files stay on screen (health data).
                return _json({
                    "memberId": p.member_id,
                    "firstName": registration.first_name,
                    "lastName": registration.last_name,
                    "tier": card["tier_name"],
                    "amount": _euros(card["amount"]),
                    "discountCode": card["discount_code"],
                    "helloassoState": card["state"],
                    "payment": payment_status(registration),
                    "orderDate": card["order_date"],
                    "photo": card["photo"],
                    "payer": {"name": card["payer_name"], "email": card["payer_email"]},
                    "hasPhone": contact.phone(registration) is not None,
                    "payments": [
                        {"date": x.get("date"), "amount": _euros(x.get("amount")), "state": x.get("state"),
                         "means": x.get("means"), "installment": x.get("installment"),
                         "cashOutState": x.get("cash_out_state"), "cashOutDate": x.get("cash_out_date")}
                        for x in card["payments"]
                    ],
                    "messages": [
                        {"kind": m["kind"], "at": m["at"], "subject": m["subject"], "body": m["body"][:300],
                         "sent": m["sent"], "error": m["error"]}
                        for m in card["messages"][:20]
                    ],
                    "check": card["check"],
                })
            table = receiver.adherents(org_id, db=db, appelant=compte)
            if not table.imposed:
                return _json({"season": found.nom, "imposed": False,
                              "note": "Pas de campagne HelloAsso pour cette saison."})
            registrations = imposed_members._by_member(db, org_id, found.id)
            names = {c.id: c for c in db.scalars(select(Compte).where(Compte.id.in_(list(table.members))))}
            text = (p.text or "").casefold().strip()
            rows = []
            for member_id, row in sorted(table.members.items(), key=lambda m: m[1].rank):
                r = imposed_members._main(registrations[member_id])
                fiche = names.get(member_id)
                first, last = (fiche.prenom, fiche.nom) if fiche else (r.first_name, r.last_name)
                status = payment_status(r)
                if text and text not in f"{first} {last} {r.payer_email or ''}".casefold():
                    continue
                if p.status == "à vérifier":
                    if row.check is None or row.check["ok"]:
                        continue
                elif p.status and p.status != status:
                    continue
                rows.append({
                    "memberId": member_id, "firstName": first, "lastName": last, "email": r.payer_email,
                    "amount": _euros(row.amount), "discountCode": row.discount_code, "payment": status,
                    "check": row.check, "mails": row.mails, "sms": row.sms, "hasPhone": row.has_phone,
                })
        return _json({
            "season": found.nom,
            "campaign": table.form_name,
            "members": len([m for m in table.members.values() if not m.cancelled]),
            "checksOn": table.checks_on,
            "count": len(rows),
            "lines": rows[: p.limit],
            "presetMessages": {kind: contact.templates(db, org_id, kind)[:20] for kind in contact.KINDS},
        })

    def read_money(db: Session, compte, org_id: int, p: SeasonOnly) -> str:
        found = season(db, org_id, p.season)
        with in_season(db, org_id, found):
            unpaid = receiver.impayes(org_id, db=db, appelant=compte)
        if not unpaid.campaign:
            return _json({"season": found.nom, "campaign": False,
                          "note": "Pas de campagne HelloAsso pour cette saison."})
        stats = statistics(db, org_id, found, sources, roles.has_right(compte, roles.DROIT_FINANCIER))
        upcoming = [
            {"memberId": u.member_id, "name": f"{u.first_name} {u.last_name}", "date": (u.date or "")[:10],
             "amount": _euros(u.amount), "installment": u.installment, "overdue": u.overdue}
            for u in unpaid.upcoming
        ]
        return _json({
            "season": found.nom,
            # « 1. À payer à HelloAsso » (Admin › À encaisser).
            "toPayToHelloasso": {
                "overdue": sum(1 for u in upcoming if u["overdue"]),
                "total": sum(u["amount"] for u in upcoming),
                "lines": upcoming[:200],
            },
            # Impayés : au moins une échéance refusée ou en échec.
            "unpaid": [
                {"memberId": m.member_id, "name": f"{m.first_name} {m.last_name}", "email": m.email,
                 "total": _euros(m.total), "unpaid": _euros(m.unpaid),
                 "refused": [{"date": (x.date or "")[:10], "amount": _euros(x.amount)} for x in m.refused]}
                for m in unpaid.members[:200]
            ],
            # « Statistiques des adhérents de la saison » : euros ; versements
            # arrivés (cash.on_account), en route, gardés par HelloAsso, à venir.
            # Soldes et projection seulement avec l'Accès au Financier.
            "statistics": stats,
        })

    return [
        Action(
            name="helloasso_campaign",
            module="HelloAsso",
            description="HelloAsso d'une saison (Admin › École › Saisons › Éditer la saison ; Admin › Élèves › ⋮ › "
            "Champs) : connecté ou non, choix de la saison (HelloAsso fait tout, L'appli fait tout HelloAsso "
            "encaisse, Sans HelloAsso), campagne choisie, dernière recopie, et la liste des campagnes HelloAsso "
            "(administrateur principal). Jamais les clés.",
            params=Campaign,
            prepare=None,
            read=read_campaign,
        ),
        Action(
            name="helloasso_members",
            module="HelloAsso",
            description="Les adhérents HelloAsso d'une saison (Admin › Élèves, saison imposée par HelloAsso) : "
            "montant, code promo, statut de paiement (payé, à encaisser, impayé, résilié), vérification du "
            "dossier, mails et SMS déjà envoyés, et les messages préenregistrés. Avec member_id : sa fiche "
            "HelloAsso (paiements, payeur, messages envoyés, vérification), sans les réponses au formulaire.",
            params=Members,
            prepare=None,
            read=read_members,
        ),
        Action(
            name="helloasso_money",
            module="HelloAsso",
            description="L'argent HelloAsso d'une saison : Admin › À encaisser (échéances à payer, dépassées), "
            "les impayés (échéances refusées), et les Statistiques des adhérents de la saison (majeurs, "
            "mineurs, prix moyen, versements arrivés sur le compte, en route, gardés par HelloAsso ; soldes et "
            "solde projeté avec l'Accès au Financier). Montants en euros.",
            params=SeasonOnly,
            prepare=None,
            read=read_money,
        ),
    ]
