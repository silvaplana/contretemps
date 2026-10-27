"""La synchronisation (spec/modules/helloasso.md §4) : chaque inscrit de la
campagne de la saison en cours devient une fiche de la saison, complétée si
la personne en a déjà une (même nom et prénom, sinon même email), créée
sinon ; ses réponses vont dans les champs de la campagne, sa formule et ses
paiements dans `helloasso_registrations`. Rien n'est renvoyé vers HelloAsso.
Toutes les 5 minutes (app/relance_worker.py) et par « Synchroniser
maintenant »."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timezone

from comptes import Compte, Comptes, roles
from members import fields as member_fields
from members import values as member_values
from saisons import saison_courante_id
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import api
from .campaign import SOURCE, Campaigns
from .connection import Connection
from .models import HelloAssoRegistration, OrgHelloAsso

# Une ligne annulée ou remboursée n'est plus une inscription.
CANCELLED = ("Canceled", "Refunded", "Deleted", "Abandoned")
_DATE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")


@dataclass
class Result:
    created: int = 0
    completed: int = 0
    updated: int = 0
    gone: int = 0


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _key(text: str | None) -> str:
    sans_accents = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return " ".join(sans_accents.lower().split())


def fix_short_year(year: int, today: date | None = None) -> int:
    """Une année saisie sur 2 chiffres (« 05/11/0017 », vu dans Sambo Admin) :
    le siècle en cours si elle n'est pas dans le futur, sinon le précédent."""
    if year >= 100:
        return year
    current = (today or date.today()).year
    year += current - current % 100
    return year - 100 if year > current else year


def answer_value(fmt: str, answer):
    """La réponse HelloAsso dans le format du champ ; telle quelle sinon."""
    if answer is None or answer == "":
        return None
    text = str(answer).strip()
    if fmt == "date":
        match = _DATE.match(text)
        if match:
            day, month, year = (int(x) for x in match.groups())
            try:
                return date(fix_short_year(year), month, day).isoformat()
            except ValueError:
                return text
        return text[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", text) else text
    if fmt == "yes_no":
        return _key(text) in ("oui", "yes", "true", "1")
    if fmt == "number":
        try:
            number = float(text.replace(",", "."))
        except ValueError:
            return text
        return int(number) if number.is_integer() else number
    return text


class Sync:
    def __init__(
        self,
        add_member: Callable[[Session, int, str, str, str | None], Compte],
        orders: Callable[[str, str, str, str, str], list[dict]] = api.orders,
    ) -> None:
        # add_member(db, org_id, nom, prénom, email) : la fiche d'élève de
        # l'appli (complète une fiche non élève du même nom). `orders` est
        # remplaçable dans les tests (pas d'appel réseau).
        self.add_member = add_member
        self.orders = orders

    @staticmethod
    def _season_members(db: Session, org_id: int, season_id: int) -> list[Compte]:
        return list(db.scalars(select(Compte).where(Compte.ecole_id == org_id, Compte.saison_id == season_id)))

    def _member_for(self, db: Session, org_id: int, season_id: int, item: dict) -> tuple[Compte, bool]:
        """La fiche de cet inscrit : (fiche, créée ?)."""
        members = self._season_members(db, org_id, season_id)
        same_name = [
            m for m in members
            if (_key(m.nom), _key(m.prenom)) == (_key(item["last_name"]), _key(item["first_name"]))
        ]
        found = same_name[0] if len(same_name) == 1 else None
        if found is None and not same_name and item["payer_email"]:
            # Même email et même prénom (nom écrit autrement) : jamais le seul
            # email, que partagent les enfants d'un même payeur.
            email, first_name = _key(item["payer_email"]), _key(item["first_name"])
            by_email = [
                m for m in members if _key(m.prenom) == first_name and email in (_key(e) for e in m.emails)
            ]
            found = by_email[0] if len(by_email) == 1 else None
        if found is not None and roles.is_eleve(found):
            return found, False
        # add_member complète une fiche non élève du même nom (un prof, un
        # membre du bureau ; jamais un admin avec un email nouveau), sinon
        # en crée une.
        member = self.add_member(db, org_id, item["last_name"], item["first_name"], item["payer_email"])
        return member, found is None or member.id != found.id

    def run(self, db: Session, org_id: int) -> Result:
        """Synchronise la saison en cours (HelloAssoError si ce n'est pas
        possible). Valide (commit)."""
        season_id = saison_courante_id(db, org_id)
        campaign = Campaigns.current(db, season_id) if season_id else None
        if campaign is None:
            raise api.HelloAssoError("Choisissez d’abord la campagne HelloAsso de la saison (Élèves > Champs).")
        connection = Connection.row(db, org_id)
        if connection is None or not connection.active:
            raise api.HelloAssoError("HelloAsso n’est pas connecté.")
        items = self.orders(*Campaigns._keys(connection), campaign.form_type, campaign.form_slug)

        season_fields = member_fields.fields(db, org_id, season_id)
        fields = [f for f in season_fields if f.source == SOURCE]
        by_id = {f.source_key: f for f in fields}
        by_label = {_key(f.label): f for f in fields}
        # Nos champs du même intitulé, cachés par ceux de la campagne, en
        # reçoivent aussi la réponse : la date de naissance donne l'âge.
        ours = {_key(f.label): f for f in season_fields if f.source is None}
        registrations = {
            r.item_id: r
            for r in db.scalars(select(HelloAssoRegistration).where(HelloAssoRegistration.season_id == season_id))
        }
        result, now, seen = Result(), _now(), set()
        for item in items:
            if item["state"] in CANCELLED or not (item["first_name"] or item["last_name"]):
                continue
            seen.add(item["item_id"])
            registration = registrations.get(item["item_id"])
            member = db.get(Compte, registration.member_id) if registration and registration.member_id else None
            if member is None or member.saison_id != season_id:
                member, created = self._member_for(db, org_id, season_id, item)
                if created:
                    result.created += 1
                else:
                    result.completed += 1
            else:
                result.updated += 1
            registration = registration or HelloAssoRegistration(
                org_id=org_id, season_id=season_id, item_id=item["item_id"]
            )
            registration.member_id = member.id
            for key in ("order_id", "first_name", "last_name", "payer_email", "tier_name", "amount",
                        "discount_code", "state", "order_date", "payments"):
                setattr(registration, key, item[key])
            registration.gone_at, registration.synced_at = None, now
            db.add(registration)
            if item["payer_email"]:
                member.payer_email = item["payer_email"]
            for answer in item["answers"]:
                field = by_id.get(answer["id"]) or by_label.get(_key(answer["name"]))
                if field is None or field.format in ("file", "group"):
                    continue
                value = answer_value(field.format, answer["answer"])
                member_values.set_external(db, member, field, value)
                twin = ours.get(_key(field.label))
                if twin is not None and twin.format == field.format:
                    member_values.set_external(db, member, twin, value)
        for registration in registrations.values():
            if registration.item_id not in seen and registration.gone_at is None:
                registration.gone_at = now
                result.gone += 1
        campaign.synced_at = now
        db.commit()
        # Famille = même email du payeur (spec/core.md §4.4).
        Comptes().recalculer_familles(db, org_id)
        db.commit()
        return result


def sync_all(db: Session, sync: Sync) -> dict[int, Result | str]:
    """Le passage du worker : chaque organisation connectée, module allumé,
    dont la saison en cours a une campagne. {organisation: résultat ou
    message d'erreur} ; une erreur n'arrête pas les autres."""
    from registry.activation import disabled

    done: dict[int, Result | str] = {}
    for connection in db.scalars(select(OrgHelloAsso).where(OrgHelloAsso.active.is_(True))):
        org_id = connection.org_id
        season_id = saison_courante_id(db, org_id)
        if "helloasso" in disabled(db, org_id) or season_id is None or Campaigns.current(db, season_id) is None:
            continue
        try:
            done[org_id] = sync.run(db, org_id)
        except Exception as erreur:  # noqa: BLE001 (les autres organisations passent)
            db.rollback()
            done[org_id] = str(erreur)
    return done
