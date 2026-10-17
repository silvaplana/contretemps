"""Ce dont le module a besoin de l'appli hôte, sans la connaître (même
principe que documents/ports.py). Contretemps les branche dans
notes_frais_contretemps/adapter.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class Membre:
    """La personne qui appelle, vue par le module. `person_id` reste le même
    d'une saison à l'autre ; `emails` : toutes ses adresses."""

    person_id: int
    org_id: int
    nom: str
    emails: tuple[str, ...] = ()
    est_tresorier: bool = False
    est_superuser: bool = False


@dataclass(frozen=True)
class Personne:
    """Une personne de l'organisation, avec de quoi la prévenir :
    ses adresses et l'identifiant à notifier dans l'appli."""

    person_id: int
    nom: str
    emails: tuple[str, ...] = ()
    notification_id: int | None = None
    role: str = ""


@dataclass(frozen=True)
class Organisation:
    nom: str
    adresse_web: str
    email_contact: str | None = None
    email_tresorier: str | None = None


@dataclass(frozen=True)
class TicketLu:
    """Ce que la lecture d'un justificatif renvoie (§12) ; tout peut manquer."""

    date: str | None = None
    montant_centimes: int | None = None
    commercant: str | None = None
    categorie: str | None = None
    description: str | None = None


class Annuaire(Protocol):
    def personnes(self, db: Session, org_id: int, person_ids: set[int]) -> dict[int, Personne]:
        """Les personnes demandées, avec leurs adresses d'aujourd'hui."""

    def tresoriers(self, db: Session, org_id: int) -> list[Personne]:
        """Les trésoriers actuels de l'organisation."""

    def organisation(self, db: Session, org_id: int) -> Organisation: ...


class Messager(Protocol):
    def envoyer(
        self, db: Session, org_id: int, a: list[str], sujet: str, texte: str, html: str, repondre_a: str | None
    ) -> None:
        """Envoie un mail au nom de l'organisation ; ne lève jamais."""


class Notifieur(Protocol):
    def notifier(self, db: Session, notification_id: int, titre: str, corps: str) -> None:
        """Notification dans l'appli ; ne lève jamais."""


class LecteurTicket(Protocol):
    @property
    def actif(self) -> bool: ...

    def lire(self, db: Session, org_id: int, contenu: bytes, type_mime: str, categories: list[str]) -> TicketLu:
        """Lit un justificatif. Lève LectureImpossible (message montrable)."""


class Classeur(Protocol):
    """Range une note validée dans les documents de l'organisation (§7 bis :
    Docs › Privé › Saison › Financier › Notes de frais)."""

    def classer(self, db: Session, tresorier: Membre, dossier: str, fichiers: list[tuple[str, Path]]) -> None:
        """Crée le dossier `dossier` et y copie les fichiers (nom, chemin)."""


class LectureImpossible(Exception):
    """La lecture n'a pas eu lieu ; le formulaire se remplit à la main."""


# Catégories proposées à une organisation qui n'en a pas encore (§4.6).
CATEGORIES_PAR_DEFAUT = ("Costumes", "Déplacement", "Matériel", "Location de salle", "Alimentation", "Autre")


@dataclass
class Ports:
    annuaire: Annuaire
    messager: Messager
    notifieur: Notifieur
    lecteur: LecteurTicket | None = None
    classeur: Classeur | None = None
    categories_par_defaut: tuple[str, ...] = field(default=CATEGORIES_PAR_DEFAUT)
