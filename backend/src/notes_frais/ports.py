"""Ce dont le module a besoin de l'appli hôte, sans la connaître (même
principe que documents/ports.py). Contretemps les branche dans
notes_frais_contretemps/adapter.py.
"""

from __future__ import annotations

from collections.abc import Callable
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
    """Ce que la lecture d'un justificatif renvoie (§12) ; tout peut manquer.
    `sorte` : « facture » (facture, reçu, ticket, avis d'échéance),
    « virement » (preuve d'un virement fait : ordre, avis d'opération),
    « vente » (une recette : remise de chèques, reçu ou facture émis par
    l'association), « salaire » (un bulletin de salaire : `salarie`, brut, net
    payé et cotisations de l'employeur) ou « autre ». `commercant` = qui a émis la pièce ; `emetteur_personne` :
    c'est une personne (auto-entrepreneur), pas une société ; `client` : à qui
    elle est adressée. Pour un virement : `beneficiaire`, `iban`, `motif`."""

    date: str | None = None
    montant_centimes: int | None = None
    commercant: str | None = None
    categorie: str | None = None
    description: str | None = None
    sorte: str = "facture"
    emetteur_personne: bool | None = None
    client: str | None = None
    beneficiaire: str | None = None
    iban: str | None = None
    motif: str | None = None
    # Une remise de chèques détaillée (financier.md §8.12) : (nom écrit, centimes) de chaque chèque.
    cheques: tuple[tuple[str, int], ...] = ()
    # Aucune catégorie ne convient : (numéro, libellé) du compte du plan à créer (financier.md §8.2 bis).
    compte_propose: tuple[str, str] | None = None
    salarie: str | None = None
    brut_centimes: int | None = None
    net_centimes: int | None = None
    employeur_centimes: int | None = None


class Annuaire(Protocol):
    def personnes(self, db: Session, org_id: int, person_ids: set[int]) -> dict[int, Personne]:
        """Les personnes demandées, avec leurs adresses d'aujourd'hui."""

    def tresoriers(self, db: Session, org_id: int) -> list[Personne]:
        """Les trésoriers actuels de l'organisation."""

    def toutes(self, db: Session, org_id: int, le: date | None = None) -> list[Personne]:
        """Toutes les personnes actuelles de l'organisation, par nom ; `le` :
        celles de la période qui contient ce jour (le prof d'une facture de
        l'an dernier), à défaut les actuelles."""

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

    def lire(self, db: Session, org_id: int, contenu: bytes, type_mime: str, categories: list[str], nom: str = "") -> TicketLu:
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

    def sous_dossiers(self, db: Session, membre: Membre, chemin: list[str]) -> list[str]:
        """The folder names under `chemin` (under Financier) in the current
        season, to choose where receipts go (financier.md §8.13)."""


@dataclass(frozen=True)
class OperationBancaire:
    """Une opération d'un compte en banque de l'organisation (centimes,
    négatif = débit)."""

    id: int
    date: date
    libelle: str
    montant_centimes: int
    compte: str = ""
    # Le numéro du compte de banque au plan comptable (512x), s'il est connu.
    compte_plan: str = ""


class Banque(Protocol):
    def debits(self, db: Session, org_id: int, montant_centimes: int, depuis: date) -> list[OperationBancaire]:
        """Les débits de ce montant (positif) depuis cette date, tous comptes."""

    def tous_debits(self, db: Session, org_id: int, depuis: date) -> list[OperationBancaire]:
        """Tous les débits depuis cette date, tous comptes (paiement possible
        à un autre montant, virement groupé)."""

    def operation(self, db: Session, org_id: int, operation_id: int) -> OperationBancaire | None: ...

    def cloturee(self, db: Session, org_id: int, jour: date) -> bool:
        """La saison qui contient ce jour est clôturée : ses lignes ne bougent plus."""

    # Ventes (financier.md §8.12) : encaisser = un crédit, ou la caisse.

    def credits(self, db: Session, org_id: int, montant_centimes: int, depuis: date) -> list[OperationBancaire]:
        """Les crédits de ce montant depuis cette date, tous comptes, hors virements internes."""

    def tous_credits(self, db: Session, org_id: int, depuis: date) -> list[OperationBancaire]:
        """Tous les crédits depuis cette date, tous comptes, hors virements internes."""

    def ventiler(self, db: Session, org_id: int, operation_id: int, lignes: list[tuple[str, int]], person_id: int) -> None:
        """La vente rattachée donne ses comptes (numéro, centimes) à la ligne
        de banque, si elle n'en a pas encore et que la somme fait la banque."""

    def deventiler(self, db: Session, org_id: int, operation_id: int, lignes: list[tuple[str, int]]) -> None:
        """Vente détachée : retire les comptes de la ligne s'ils sont ceux de la vente."""

    def entrer_en_caisse(self, db: Session, org_id: int, jour: date, libelle: str, lignes: list[tuple[str, int]], person_id: int) -> None:
        """Vente encaissée en espèces : une ligne de caisse par compte."""

    def sortir_de_caisse(self, db: Session, org_id: int, jour: date, libelle: str) -> None:
        """Défait `entrer_en_caisse` (les lignes de ce jour à ce libellé)."""


class LectureImpossible(Exception):
    """La lecture n'a pas eu lieu ; le formulaire se remplit à la main."""


# Catégories proposées à une organisation qui n'en a pas encore (§4.6).
CATEGORIES_PAR_DEFAUT = ("Costumes", "Déplacement", "Matériel", "Location de salle", "Alimentation", "Autre")


@dataclass(frozen=True)
class Saison:
    """A season of the host (Emplacement des pièces manuelles, §8.13: one setting per season)."""

    id: int
    nom: str
    debut: date
    fin: date


@dataclass
class Ports:
    annuaire: Annuaire
    messager: Messager
    notifieur: Notifieur
    lecteur: LecteurTicket | None = None
    classeur: Classeur | None = None
    banque: Banque | None = None
    categories_par_defaut: tuple[str, ...] = field(default=CATEGORIES_PAR_DEFAUT)
    # Le plan comptable de l'hôte : (numéro, libellé) des comptes de charges
    # actifs. Quand il est là, les catégories en sont le reflet (§4.6).
    plan: Callable[[Session, int], list[tuple[str, str]]] | None = None
    # Les comptes d'une vente (financier.md §8.12) : (numéro, libellé) des
    # comptes de produits actifs ; ils deviennent des catégories à part.
    plan_ventes: Callable[[Session, int], list[tuple[str, str]]] | None = None
    # Créer (ou réactiver) un compte du plan proposé par la lecture : (db, org_id,
    # numéro, libellé, recette ?) ; la catégorie suit (financier.md §8.2 bis).
    creer_compte: Callable[[Session, int, str, str, bool], None] | None = None
    # La paie (financier.md §8.11) : les comptes d'un bulletin de salaire (641, 645, 431) qui
    # manquent au plan, (numéro, libellé) ; les y ajouter (« L'association a des salariés » :
    # oui), ou retirer 431 (non). La paie est allumée quand 431 est dans le plan.
    paie_manquants: Callable[[Session, int], list[tuple[str, str]]] | None = None
    ajouter_paie: Callable[[Session, int], None] | None = None
    retirer_paie: Callable[[Session, int], None] | None = None
    # Le compte de tiers (numéro, libellé) d'une pièce de cette nature pour ce
    # nom (401 Fournisseurs, 467n Honoraires Nom ; numéro vide = créé à la
    # validation), None si l'hôte ne passe pas par les tiers. Il fait montrer
    # les écritures de la pièce à la revue de l'import (Seb, 10/11).
    tiers: Callable[[Session, int, str, str], tuple[str, str] | None] | None = None
    # Importation automatique de pièces : le fichier d'un justificatif resté sur un drive du
    # club (db, org_id, drive_id, chemin) → chemin d'une copie temporaire à
    # servir. None : l'hôte n'a pas de drives.
    drive: Callable[[Session, int, int, str], Path] | None = None
    # Emplacement des pièces manuelles (financier.md §8.13): puts a file on a
    # club drive (db, org_id, drive_id, chosen folder, sub-folders, name,
    # content, mime, date of the receipt) in chosen folder › season of the
    # date › sub-folders, creating what is missing; returns its path on the
    # drive. None: the host has no drives.
    deposer: Callable[[Session, int, int, str, list[str], str, bytes, str, date | None], str] | None = None
    # The school's seasons, for one place per season (financier.md §8.13).
    # None: the host has no seasons, one setting for all.
    saisons: Callable[[Session, int], list[Saison]] | None = None
