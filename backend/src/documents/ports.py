"""Ce dont le module a besoin de l'appli hôte, sans la connaître (plan §1
règle 2). Contretemps les branche dans documents_contretemps/adapter.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class Member:
    """La personne qui appelle, vue par le module.

    `person_id` reste le même d'une saison à l'autre (dans Contretemps, les
    comptes sont recopiés à chaque saison : c'est l'id du premier compte de
    la chaîne, plan §1 règle 6). `groups` contient toutes les clés de
    groupe dont elle fait partie, rôles compris ("role:admin", "course:12").
    """

    person_id: int
    org_id: int
    display_name: str
    is_admin: bool = False
    is_superuser: bool = False
    # Peut avoir un espace Personnel (pas les élèves, Seb 15 octobre).
    has_personal_space: bool = False
    groups: frozenset[str] = field(default_factory=frozenset)
    # The address the person signed in with (or their first one): used to
    # send a trial to oneself, also for a superuser outside the school.
    email: str | None = None


@dataclass(frozen=True)
class Principal:
    """Une personne ou un groupe, tel qu'affiché dans « Qui a accès ? »."""

    type: str  # "member" | "group"
    id: str
    label: str
    detail: str = ""


@dataclass(frozen=True)
class Recipient:
    """Une personne à qui envoyer un fichier (Diffuser) ; `email` vide :
    rien ne peut lui partir."""

    person_id: int
    name: str
    email: str | None


@dataclass(frozen=True)
class Period:
    id: int
    name: str
    is_current: bool


class Directory(Protocol):
    """Personnes et groupes de l'organisation."""

    def describe(self, db: Session, org_id: int, principals: list[tuple[str, str]]) -> dict[tuple[str, str], Principal]:
        """Libellés des personnes et groupes donnés (type, id)."""

    def search(self, db: Session, org_id: int, query: str, limit: int = 20) -> list[Principal]:
        """Groupes puis personnes dont le nom contient `query` (tous si vide)."""

    def person_names(self, db: Session, org_id: int, person_ids: set[int]) -> dict[int, str]:
        """Nom affiché de chaque personne (auteurs, historique)."""

    def recipients(self, db: Session, org_id: int, principals: list[tuple[str, str]]) -> list[Recipient]:
        """Les personnes derrière des personnes et groupes (type, id), chacune
        une fois, avec son adresse email d'aujourd'hui (Diffuser)."""


class Mailer(Protocol):
    """Envoi des emails du module (Diffuser), branché par l'appli hôte."""

    @property
    def available(self) -> bool:
        """Un email peut-il partir de ce serveur ?"""

    def org(self, db: Session, org_id: int) -> tuple[str, str]:
        """(nom de l'organisation, adresse web de son appli, sans / final)."""

    def send(self, to: str, subject: str, text: str, html: str, sender_name: str, reply_to: str | None) -> None:
        """Envoie ou lève une exception (message lisible)."""


class Notifier(Protocol):
    """Notifications sur le téléphone, branchées par l'appli hôte (dépôt dans
    un bac Échanges, §4.7 ter)."""

    def notify(self, db: Session, org_id: int, person_ids: list[int], title: str, body: str) -> None:
        """Prévient ces personnes ; ne lève jamais d'exception."""


class Periods(Protocol):
    """Saisons (ou exercices) de l'organisation."""

    def list(self, db: Session, org_id: int) -> list[Period]:
        """Toutes les périodes, de la plus ancienne à la plus récente."""


# Rôles qui ont l'Écriture dans l'espace Privé par défaut (§4.4 règle 4 :
# admins et professeurs, Seb 15 octobre). L'appli hôte peut en donner
# d'autres : ce sont des clés de groupe.
DEFAULT_PRIVATE_EDITORS = ("role:admin", "role:professeur")
