"""Ce dont le module a besoin de l'appli hôte, sans la connaître (même
principe que documents/ports.py). Contretemps les branche dans
notes_frais_contretemps/adapter.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
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
    # Trésorier qui agit au nom de la personne (§7 ter) : son person_id.
    agissant_id: int | None = None


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

    def toutes(self, db: Session, org_id: int) -> list[Personne]:
        """Toutes les personnes actuelles de l'organisation, par nom."""

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
    """Range les justificatifs dans les documents de l'organisation, dossier
    Financier de la saison (§7 bis, financier.md §8.3 bis) : un seul endroit,
    l'état ne se lit que dans l'appli. `le` = date de la pièce : la saison
    qui la contient, sinon la saison en cours."""

    def classer(
        self,
        db: Session,
        membre: Membre,
        chemin: list[str],
        fichiers: list[tuple[str, Path]],
        remplacer: set[str] = frozenset(),
        reprendre: bool = False,
        le: date | None = None,
    ) -> list[int]:
        """`chemin` = dossiers sous Financier (ex. [« Notes de frais »,
        personne, note] ou [« Achats »]). Crée ce qu'il manque et y copie les
        fichiers (nom, chemin) ; un nom déjà pris devient « nom (2) ». Ceux de
        `remplacer` déjà là reçoivent une nouvelle version ; avec `reprendre`,
        un fichier déjà là est gardé tel quel (reprise des anciennes
        enveloppes). Renvoie l'id de chaque fichier."""

    def deplacer(
        self, db: Session, membre: Membre, chemin: list[str], fichiers: list[tuple[int, str]], le: date | None = None
    ) -> None:
        """Remet ailleurs des justificatifs déjà rangés (id, nom), quand la
        date, la personne ou le fournisseur est corrigé ; le dossier de note
        resté vide part à la corbeille."""

    def contenu(self, db: Session, membre: Membre, node_id: int) -> Path:
        """Le fichier sur le disque d'un justificatif rangé (LookupError sinon)."""

    def retirer(
        self, db: Session, membre: Membre, chemin: list[str], node_ids: list[int] = (), le: date | None = None
    ) -> None:
        """Met à la corbeille le dossier `chemin` (note reprise par son
        auteur), ou seulement les fichiers `node_ids` quand ils sont rangés
        directement dans un dossier commun (Achats)."""


@dataclass(frozen=True)
class OperationBancaire:
    """Une opération d'un compte en banque de l'organisation (centimes,
    négatif = débit)."""

    id: int
    date: date
    libelle: str
    montant_centimes: int
    compte: str = ""


class Banque(Protocol):
    def debits(self, db: Session, org_id: int, montant_centimes: int, depuis: date) -> list[OperationBancaire]:
        """Les débits de ce montant (positif) depuis cette date, tous comptes."""

    def operation(self, db: Session, org_id: int, operation_id: int) -> OperationBancaire | None: ...


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
    banque: Banque | None = None
    categories_par_defaut: tuple[str, ...] = field(default=CATEGORIES_PAR_DEFAUT)
