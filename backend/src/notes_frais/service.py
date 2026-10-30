"""Règles du module notes de frais (spec/modules/notes-de-frais.md).

Erreurs : `LookupError` (introuvable, 404), `PermissionError` (pas le
droit, 403), `ValueError` (saisie refusée, 400) ; le message est montrable
tel quel. Les droits sont vérifiés ici, pas dans les routes : la personne
ne touche que ses dépenses et ses notes, les trésoriers voient et traitent
toutes celles de l'organisation (§11).
"""

from __future__ import annotations

import html
import io
import logging
import re
import unicodedata
import zipfile
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    ACHAT,
    ENVOYEE,
    FRAIS,
    HONORAIRES,
    NATURES,
    PERSONNE_A_CHOISIR,
    PREPAREE,
    REFUSEE,
    REMBOURSEE,
    VALIDEE,
    VIREE,
    CategorieFrais,
    Depense,
    NoteFrais,
    Payer,
    PieceJustificative,
    Rib,
)
from .ports import LectureImpossible, Membre, OperationBancaire, Personne, Ports, TicketLu
from . import recapitulatif
from .stockage import StockageEnveloppes, nom_dossier, nom_propre

logger = logging.getLogger(__name__)

TYPES_ACCEPTES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/heic", "image/heif", "application/pdf"}
PIECES_MAX = 5
MONTANT_MAX_CENTIMES = 10_000_000  # 100 000 €, garde-fou contre une virgule oubliée

FILTRES = ("a_valider", "a_rembourser", "terminees")
# À payer, pas encore vu sur le compte (financier.md §8.3 bis).
EN_PAIEMENT = (VALIDEE, PREPAREE, VIREE)
# Dossiers de Docs › Financier, par nature (financier.md §8.3 bis).
DOSSIERS = {FRAIS: "Notes de frais", HONORAIRES: "HONORAIRES", ACHAT: "ACHATS"}
MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
        "novembre", "décembre")
MOIS_COURTS = ("janv", "fevr", "mars", "avr", "mai", "juin", "juil", "aout", "sept", "oct", "nov", "dec")
_EXTENSIONS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif",
               "image/heic": ".heic", "image/heif": ".heif", "application/pdf": ".pdf"}


def _maintenant() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def euros(centimes: int) -> str:
    """12345 -> « 123,45 € » (espace insécable avant les milliers)."""
    entier, reste = divmod(abs(centimes), 100)
    groupe = f"{entier:,}".replace(",", " ")
    return f"{'-' if centimes < 0 else ''}{groupe},{reste:02d} €"


def montant_court(centimes: int) -> str:
    """12345 -> « 123,45 » (nom de fichier, presse-papier)."""
    return f"{centimes // 100},{centimes % 100:02d}"


def _sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texte or "") if not unicodedata.combining(c)).casefold()


def normaliser_iban(iban: str | None) -> str | None:
    """Sans espaces, en majuscules, clé de contrôle vérifiée (ISO 13616)."""
    texte = "".join((iban or "").split()).upper()
    if not texte:
        return None
    if not (15 <= len(texte) <= 34 and texte[:2].isalpha() and texte[2:4].isdigit() and texte.isalnum()):
        raise ValueError("Cet IBAN n'a pas la bonne forme (ex. FR76 3000 6000 0112 3456 7890 189).")
    if int("".join(str(int(c, 36)) for c in texte[4:] + texte[:4])) % 97 != 1:
        raise ValueError("Cet IBAN est incorrect : un caractère est sans doute mal recopié.")
    return texte


def normaliser_bic(bic: str | None) -> str | None:
    texte = "".join((bic or "").split()).upper()
    if not texte:
        return None
    if not re.fullmatch(r"[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?", texte):
        raise ValueError("Ce BIC n'a pas la bonne forme (8 ou 11 caractères, ex. AGRIFRPP).")
    return texte


class NotesDeFrais:
    def __init__(self, ports: Ports, stockage: StockageEnveloppes) -> None:
        self.ports = ports
        self.stockage = stockage

    # --- Catégories (§4.6) ---

    def categories(self, db: Session, org_id: int, *, toutes: bool = False) -> list[CategorieFrais]:
        existantes = list(
            db.scalars(select(CategorieFrais).where(CategorieFrais.org_id == org_id).order_by(CategorieFrais.ordre, CategorieFrais.id))
        )
        if not existantes:
            for ordre, libelle in enumerate(self.ports.categories_par_defaut):
                db.add(CategorieFrais(org_id=org_id, libelle=libelle, ordre=ordre))
            db.commit()
            return self.categories(db, org_id, toutes=toutes)
        return existantes if toutes else [c for c in existantes if c.active]

    def definir_categories(self, db: Session, membre: Membre, libelles: list[str]) -> list[CategorieFrais]:
        """Trésoriers : la liste voulue, dans l'ordre. Une catégorie qui
        disparaît est seulement désactivée (elle reste sur les anciennes
        dépenses) ; un libellé déjà connu est réactivé."""
        self._exiger_tresorier(membre)
        propres = []
        for libelle in libelles:
            libelle = " ".join(libelle.split())[:60]
            if libelle and libelle.lower() not in {p.lower() for p in propres}:
                propres.append(libelle)
        if not propres:
            raise ValueError("Gardez au moins une catégorie.")
        existantes = {c.libelle.lower(): c for c in self.categories(db, membre.org_id, toutes=True)}
        for categorie in existantes.values():
            categorie.active = False
        for ordre, libelle in enumerate(propres):
            categorie = existantes.get(libelle.lower())
            if categorie is None:
                db.add(CategorieFrais(org_id=membre.org_id, libelle=libelle, ordre=ordre))
            else:
                categorie.libelle, categorie.ordre, categorie.active = libelle, ordre, True
        db.commit()
        return self.categories(db, membre.org_id)

    def _categorie(self, db: Session, org_id: int, categorie_id: int | None) -> int | None:
        if categorie_id is None:
            return None
        categorie = db.get(CategorieFrais, categorie_id)
        if categorie is None or categorie.org_id != org_id:
            raise ValueError("Catégorie inconnue.")
        return categorie.id

    # --- RIB (§4.5) ---

    def rib(self, db: Session, org_id: int, person_id: int) -> Rib | None:
        return db.scalar(select(Rib).where(Rib.org_id == org_id, Rib.person_id == person_id))

    def definir_rib(self, db: Session, membre: Membre, *, titulaire: str | None, iban: str | None, bic: str | None) -> Rib | None:
        """IBAN vide : le RIB est retiré."""
        iban = normaliser_iban(iban)
        actuel = self.rib(db, membre.org_id, membre.person_id)
        if iban is None:
            if actuel is not None:
                db.delete(actuel)
                db.commit()
            return None
        if actuel is None:
            actuel = Rib(org_id=membre.org_id, person_id=membre.person_id, iban=iban)
            db.add(actuel)
        actuel.iban = iban
        actuel.bic = normaliser_bic(bic)
        actuel.titulaire = " ".join((titulaire or "").split())[:120] or None
        db.commit()
        db.refresh(actuel)
        return actuel

    # --- Dépenses (§4.2, §4.3) ---

    def _depense(self, db: Session, membre: Membre, depense_id: int, *, modifiable: bool = True) -> Depense:
        depense = db.get(Depense, depense_id)
        if depense is None or depense.org_id != membre.org_id or depense.person_id != membre.person_id:
            raise LookupError("Dépense introuvable.")
        if modifiable and depense.note_id is not None:
            raise ValueError("Cette dépense est déjà envoyée : reprenez la note pour la modifier.")
        return depense

    def _valider_saisie(self, montant_centimes: int, jour: date) -> None:
        if montant_centimes <= 0:
            raise ValueError("Le montant doit être supérieur à zéro.")
        if montant_centimes > MONTANT_MAX_CENTIMES:
            raise ValueError("Ce montant semble trop élevé : vérifiez la virgule.")
        if jour > date.today():
            raise ValueError("La date de la dépense ne peut pas être dans le futur.")

    def creer_depense(
        self,
        db: Session,
        membre: Membre,
        *,
        jour: date,
        montant_centimes: int,
        categorie_id: int | None,
        description: str,
        lue_par_ia: bool = False,
    ) -> Depense:
        self._valider_saisie(montant_centimes, jour)
        depense = Depense(
            org_id=membre.org_id,
            person_id=membre.person_id,
            date=jour,
            montant_centimes=montant_centimes,
            categorie_id=self._categorie(db, membre.org_id, categorie_id),
            description=" ".join(description.split())[:200],
            lue_par_ia=lue_par_ia,
        )
        db.add(depense)
        db.commit()
        db.refresh(depense)
        return depense

    def modifier_depense(self, db: Session, membre: Membre, depense_id: int, **champs) -> Depense:
        depense = self._depense(db, membre, depense_id)
        if "categorie_id" in champs:
            depense.categorie_id = self._categorie(db, membre.org_id, champs["categorie_id"])
        if champs.get("jour") is not None:
            depense.date = champs["jour"]
        if champs.get("montant_centimes") is not None:
            depense.montant_centimes = champs["montant_centimes"]
        if champs.get("description") is not None:
            depense.description = " ".join(champs["description"].split())[:200]
        self._valider_saisie(depense.montant_centimes, depense.date)
        db.commit()
        db.refresh(depense)
        return depense

    def supprimer_depense(self, db: Session, membre: Membre, depense_id: int) -> None:
        depense = self._depense(db, membre, depense_id)
        chemins = [p.chemin for p in depense.pieces]
        db.delete(depense)
        db.commit()
        for chemin in chemins:
            self.stockage.delete(membre.org_id, chemin)

    # --- Justificatifs ---

    def ajouter_piece(self, db: Session, membre: Membre, depense_id: int, flux: BinaryIO, nom: str, type_mime: str) -> PieceJustificative:
        depense = self._depense(db, membre, depense_id)
        if type_mime not in TYPES_ACCEPTES:
            raise ValueError("Seules les photos (JPEG, PNG, WebP, HEIC) et les PDF sont acceptés.")
        if len(depense.pieces) >= PIECES_MAX:
            raise ValueError(f"Pas plus de {PIECES_MAX} justificatifs par dépense.")
        extension = Path(nom or "").suffix.lower() or _EXTENSIONS.get(type_mime, "")
        nom_fichier = f"{depense.date.isoformat()} {depense.description or 'ticket'} {depense.id}-{len(depense.pieces) + 1}{extension}"
        dossier = self.stockage.dossier_depenses(membre.org_id, membre.person_id, membre.nom)
        chemin, taille = self.stockage.put(membre.org_id, dossier, nom_fichier, flux)
        piece = PieceJustificative(
            depense_id=depense.id, chemin=chemin, type_mime=type_mime, nom=(nom or "")[:200], taille=taille,
            ordre=len(depense.pieces),
        )
        db.add(piece)
        db.commit()
        db.refresh(piece)
        return piece

    def supprimer_piece(self, db: Session, membre: Membre, piece_id: int) -> None:
        piece = db.get(PieceJustificative, piece_id)
        if piece is None:
            raise LookupError("Justificatif introuvable.")
        self._depense(db, membre, piece.depense_id)
        chemin = piece.chemin
        db.delete(piece)
        db.commit()
        self.stockage.delete(membre.org_id, chemin)

    def _chemin_piece(self, db: Session, membre: Membre, piece: PieceJustificative) -> Path:
        """Le fichier d'un justificatif : dans Docs une fois la dépense
        envoyée, sur le disque avant."""
        if piece.doc_node_id is not None and self.ports.classeur is not None:
            return self.ports.classeur.contenu(db, membre, piece.doc_node_id)
        return self.stockage.chemin(membre.org_id, piece.chemin)

    def fichier_piece(self, db: Session, membre: Membre, piece_id: int) -> tuple[Path, str, str]:
        """(chemin, type, nom) : pour la personne elle-même ou un trésorier."""
        piece = db.get(PieceJustificative, piece_id)
        depense = piece.depense if piece is not None else None
        if depense is None or depense.org_id != membre.org_id:
            raise LookupError("Justificatif introuvable.")
        if depense.person_id != membre.person_id and not (membre.est_tresorier or membre.est_superuser):
            raise LookupError("Justificatif introuvable.")
        chemin = self._chemin_piece(db, membre, piece)
        if not chemin.exists():
            raise LookupError("Fichier du justificatif introuvable.")
        return chemin, piece.type_mime, piece.nom

    def archive_justificatifs(self, db: Session, membre: Membre, note_id: int) -> tuple[bytes, str]:
        """Zip des justificatifs d'une note (§7), pour un trésorier ou
        l'auteur : (contenu, nom du fichier), avec le PDF récapitulatif fait
        à la demande (financier.md §8.3 bis)."""
        note = self._note(db, membre.org_id, note_id)
        if note.person_id != membre.person_id and not (membre.est_tresorier or membre.est_superuser):
            raise LookupError("Note de frais introuvable.")
        tampon = io.BytesIO()
        with zipfile.ZipFile(tampon, "w", zipfile.ZIP_STORED) as archive:
            recap = self._recapitulatif(db, membre, note)
            if recap is not None:
                archive.writestr(recapitulatif.NOM_FICHIER, recap)
            for depense in note.depenses:
                for piece in depense.pieces:
                    chemin = self._chemin_piece(db, membre, piece)
                    if chemin.exists():
                        # Rangé dans Docs, `chemin` garde le nom du fichier.
                        archive.write(chemin, Path(piece.chemin).name)
        nom = nom_propre(f"{note.envoyee_le.date().isoformat()} {note.titre} ({note.id})", 100)
        return tampon.getvalue(), f"{nom}.zip"

    # --- Lecture du ticket (§12) ---

    @property
    def lecture_disponible(self) -> bool:
        return self.ports.lecteur is not None and self.ports.lecteur.actif

    def lire_ticket(self, db: Session, membre: Membre, contenu: bytes, type_mime: str) -> dict:
        """Champs pré-remplis ; la catégorie est ramenée à une de celles de
        l'organisation. Lève LectureImpossible."""
        if type_mime not in TYPES_ACCEPTES:
            raise LectureImpossible("Seules les photos et les PDF peuvent être lus.")
        if not self.lecture_disponible:
            raise LectureImpossible("La lecture automatique des tickets n'est pas disponible.")
        categories = self.categories(db, membre.org_id)
        lu: TicketLu = self.ports.lecteur.lire(db, membre.org_id, contenu, type_mime, [c.libelle for c in categories])
        par_libelle = {c.libelle.lower(): c for c in categories}
        categorie = par_libelle.get((lu.categorie or "").strip().lower())
        jour = None
        if lu.date:
            try:
                jour = date.fromisoformat(lu.date)
                if jour > date.today():
                    jour = None
            except ValueError:
                jour = None
        description = lu.description or lu.commercant or ""
        if lu.commercant and lu.description and lu.commercant.lower() not in lu.description.lower():
            description = f"{lu.description} ({lu.commercant})"
        montant = lu.montant_centimes if lu.montant_centimes and 0 < lu.montant_centimes <= MONTANT_MAX_CENTIMES else None
        return {
            "date": jour.isoformat() if jour else None,
            "montant_centimes": montant,
            "categorie_id": categorie.id if categorie else None,
            "description": description[:200],
            "commercant": (lu.commercant or "")[:120] or None,
        }

    # --- Notes : côté membre (§4.4) ---

    def _note(self, db: Session, org_id: int, note_id: int) -> NoteFrais:
        note = db.get(NoteFrais, note_id)
        if note is None or note.org_id != org_id:
            raise LookupError("Note de frais introuvable.")
        return note

    def envoyer(
        self,
        db: Session,
        membre: Membre,
        *,
        depense_ids: list[int],
        titre: str,
        don: bool,
        rib: dict | None = None,
    ) -> NoteFrais:
        """Crée la note et la transmet aux trésoriers (pas d'étape « créée
        mais pas envoyée », §4.4). `rib` : {titulaire, iban, bic}, enregistré
        aussi dans le Profil."""
        if not depense_ids:
            raise ValueError("Cochez au moins une dépense à envoyer.")
        depenses = [self._depense(db, membre, i) for i in dict.fromkeys(depense_ids)]
        if rib is not None and (rib.get("iban") or "").strip():
            self.definir_rib(db, membre, titulaire=rib.get("titulaire"), iban=rib.get("iban"), bic=rib.get("bic"))
        actuel = self.rib(db, membre.org_id, membre.person_id)
        if not don and actuel is None:
            raise ValueError("Indiquez votre RIB pour être remboursé(e), ou cochez le don à l'association.")
        titre = " ".join((titre or "").split())[:120] or f"Note du {date.today().strftime('%d/%m/%Y')}"
        note = NoteFrais(org_id=membre.org_id, person_id=membre.person_id, titre=titre, statut=ENVOYEE, don=don)
        if actuel is not None and not don:
            note.rib_titulaire, note.rib_iban, note.rib_bic = actuel.titulaire, actuel.iban, actuel.bic
        # Établie par un trésorier pour la personne (§7 ter) : validée en même
        # temps (financier.md §8.3 bis).
        if membre.agissant_id is not None:
            note.statut, note.traitee_le, note.traitee_par = VALIDEE, _maintenant(), membre.agissant_id
        db.add(note)
        db.flush()
        for depense in depenses:
            depense.note_id = note.id
        db.commit()
        db.refresh(note)
        self._ranger(db, membre, note)
        if membre.agissant_id is None:
            self._prevenir_tresoriers(db, membre, note)
        return note

    def reprendre(self, db: Session, membre: Membre, note_id: int) -> None:
        """Tant qu'aucun trésorier n'a validé (ou après un refus) : la note
        disparaît et ses dépenses repassent « À envoyer » ; ses justificatifs
        quittent Docs (corbeille) pour revenir avec les dépenses."""
        note = self._note(db, membre.org_id, note_id)
        if note.person_id != membre.person_id:
            raise LookupError("Note de frais introuvable.")
        if note.statut not in (ENVOYEE, REFUSEE):
            raise ValueError("Cette note est déjà validée : elle ne peut plus être reprise.")
        dossier = self.stockage.dossier_depenses(membre.org_id, membre.person_id, membre.nom)
        rangees = []
        for depense in note.depenses:
            for piece in depense.pieces:
                if piece.doc_node_id is None:
                    continue
                with open(self._chemin_piece(db, membre, piece), "rb") as source:
                    piece.chemin, _ = self.stockage.put(membre.org_id, dossier, Path(piece.chemin).name, source)
                rangees.append(piece.doc_node_id)
                piece.doc_node_id = None
        db.commit()
        if rangees:
            self._declasser(db, membre, note, rangees)
        for depense in list(note.depenses):
            depense.note_id = None
        db.flush()
        db.delete(note)
        db.commit()

    def espace(self, db: Session, membre: Membre) -> dict:
        """Tout ce qu'affiche « Mes notes de frais »."""
        a_envoyer = db.scalars(
            select(Depense)
            .where(Depense.org_id == membre.org_id, Depense.person_id == membre.person_id, Depense.note_id.is_(None))
            .order_by(Depense.date.desc(), Depense.id.desc())
        )
        notes = db.scalars(
            select(NoteFrais)
            .where(NoteFrais.org_id == membre.org_id, NoteFrais.person_id == membre.person_id)
            .order_by(NoteFrais.envoyee_le.desc(), NoteFrais.id.desc())
        )
        rib = self.rib(db, membre.org_id, membre.person_id)
        return {
            "a_envoyer": [self.depense_dict(d) for d in a_envoyer],
            "notes": [self.note_dict(n) for n in notes],
            "rib": self.rib_dict(rib),
            "categories": [{"id": c.id, "libelle": c.libelle} for c in self.categories(db, membre.org_id)],
            "tresoriers": len(self.ports.annuaire.tresoriers(db, membre.org_id)),
            "lecture_disponible": self.lecture_disponible,
        }

    def compteurs(self, db: Session, membre: Membre) -> dict:
        """Pour la ligne du Profil : « 3 à envoyer », « 1 en attente »."""
        a_envoyer = db.scalars(
            select(Depense.id).where(
                Depense.org_id == membre.org_id, Depense.person_id == membre.person_id, Depense.note_id.is_(None)
            )
        ).all()
        en_attente = db.scalars(
            select(NoteFrais.id).where(
                NoteFrais.org_id == membre.org_id,
                NoteFrais.person_id == membre.person_id,
                (NoteFrais.statut == ENVOYEE) | (NoteFrais.statut.in_(EN_PAIEMENT) & NoteFrais.don.is_(False)),
            )
        ).all()
        resultat = {"a_envoyer": len(a_envoyer), "en_attente": len(en_attente)}
        if membre.est_tresorier:
            resultat["a_valider"] = len(
                db.scalars(select(NoteFrais.id).where(NoteFrais.org_id == membre.org_id, NoteFrais.statut == ENVOYEE)).all()
            )
        return resultat

    # --- Notes : côté trésorier (§7) ---

    def _exiger_tresorier(self, membre: Membre) -> None:
        if not (membre.est_tresorier or membre.est_superuser):
            raise PermissionError("Réservé aux trésoriers de l'association.")

    def personnes(self, db: Session, membre: Membre) -> list[Personne]:
        """Pour qui un trésorier peut saisir (Financier › ⋯ « pour quelqu'un »)."""
        self._exiger_tresorier(membre)
        return self.ports.annuaire.toutes(db, membre.org_id)

    def agir_pour(self, db: Session, membre: Membre, person_id: int) -> Membre:
        """Le trésorier saisit et envoie pour une personne de l'organisation :
        dépenses, RIB et notes sont alors à son nom à elle."""
        self._exiger_tresorier(membre)
        personne = self.ports.annuaire.personnes(db, membre.org_id, {person_id}).get(person_id)
        if personne is None:
            raise LookupError("Personne inconnue dans cette organisation.")
        return replace(
            membre, person_id=personne.person_id, nom=personne.nom, emails=personne.emails, agissant_id=membre.person_id
        )

    def tresorerie(self, db: Session, membre: Membre, filtre: str) -> list[dict]:
        """Une puce de Financier › Pièces (une nature : les notes à valider
        d'abord), ou un des filtres d'avant (a_valider, a_rembourser,
        terminees)."""
        self._exiger_tresorier(membre)
        if filtre not in FILTRES + NATURES:
            raise ValueError("Filtre inconnu.")
        requete = select(NoteFrais).where(NoteFrais.org_id == membre.org_id)
        if filtre in NATURES:
            requete = requete.where(NoteFrais.nature == filtre).order_by(
                (NoteFrais.statut != ENVOYEE), NoteFrais.envoyee_le.desc(), NoteFrais.id.desc()
            )
        elif filtre == "a_valider":
            requete = requete.where(NoteFrais.statut == ENVOYEE).order_by(NoteFrais.envoyee_le)
        elif filtre == "a_rembourser":
            requete = requete.where(NoteFrais.statut.in_(EN_PAIEMENT), NoteFrais.don.is_(False)).order_by(NoteFrais.traitee_le)
        else:
            requete = requete.where(
                (NoteFrais.statut.in_((REMBOURSEE, REFUSEE))) | ((NoteFrais.statut == VALIDEE) & NoteFrais.don.is_(True))
            ).order_by(NoteFrais.envoyee_le.desc())
        return self.notes_dicts(db, membre, list(db.scalars(requete)))

    def notes_dicts(self, db: Session, membre: Membre, notes: list[NoteFrais]) -> list[dict]:
        """Vu du trésorier : avec les noms, et l'opération du compte qui
        semble payer la pièce (`paiement_propose`)."""
        ids = {n.person_id for n in notes} | {i for n in notes for i in (n.traitee_par, n.prepared_by, n.payer_id) if i}
        personnes = self.ports.annuaire.personnes(db, membre.org_id, ids - {PERSONNE_A_CHOISIR})
        prises = self._operations_prises(db, membre.org_id)
        resultat = []
        for note in notes:
            ligne = self.note_dict(note, personnes=personnes)
            operation = self.paiement_propose(db, note, prises)
            ligne["paiement_propose"] = operation and {
                "id": operation.id, "date": operation.date.isoformat(), "libelle": operation.libelle,
                "montant_centimes": operation.montant_centimes, "compte": operation.compte,
            }
            ligne["operation_id"] = note.bank_operation_id
            resultat.append(ligne)
        return resultat

    def compteurs_tresorerie(self, db: Session, membre: Membre) -> dict:
        """Badges des puces : ce qui attend une action de qui regarde. Par
        nature, les notes à valider ; Virements, les à payer, les préparés
        pour moi et les envoyés vus sur le compte (financier.md §8.3 bis)."""
        self._exiger_tresorier(membre)
        a_valider = db.scalars(
            select(NoteFrais.nature).where(NoteFrais.org_id == membre.org_id, NoteFrais.statut == ENVOYEE)
        ).all()
        compteurs = {nature: a_valider.count(nature) for nature in NATURES}
        en_paiement = db.scalars(
            select(NoteFrais).where(
                NoteFrais.org_id == membre.org_id, NoteFrais.don.is_(False), NoteFrais.statut.in_(EN_PAIEMENT)
            )
        ).all()
        prises = self._operations_prises(db, membre.org_id)
        compteurs["virements"] = sum(
            note.statut == VALIDEE
            or (note.statut == PREPAREE and note.payer_id == membre.person_id)
            or (note.statut == VIREE and self.paiement_propose(db, note, prises) is not None)
            for note in en_paiement
        )
        return compteurs

    def valider(self, db: Session, membre: Membre, note_id: int) -> NoteFrais:
        self._exiger_tresorier(membre)
        note = self._note(db, membre.org_id, note_id)
        if note.statut != ENVOYEE:
            raise ValueError("Cette note n'est plus à valider.")
        if note.nature == FRAIS and note.person_id == membre.person_id and any(
            t.person_id != membre.person_id for t in self.ports.annuaire.tresoriers(db, membre.org_id)
        ):
            raise PermissionError("Un autre trésorier doit valider votre propre note.")
        self._exiger_complete(note)
        note.statut, note.traitee_le, note.traitee_par = VALIDEE, _maintenant(), membre.person_id
        db.commit()
        db.refresh(note)
        if note.nature != FRAIS:
            return note
        if note.don:
            self._prevenir_auteur(db, membre, note, "validée (don à l'association)", "Merci pour votre don : votre note de frais a été validée.")
        else:
            self._prevenir_auteur(db, membre, note, "validée", "Votre note de frais a été validée ; le remboursement suivra.")
        return note

    @staticmethod
    def _exiger_complete(note: NoteFrais) -> None:
        """Une pièce photographiée en rafale se complète avant d'être validée."""
        if note.nature == HONORAIRES and note.person_id == PERSONNE_A_CHOISIR:
            raise ValueError("Choisissez d'abord pour qui sont ces honoraires.")
        if any(d.montant_centimes <= 0 for d in note.depenses):
            raise ValueError("Indiquez d'abord le montant.")

    # --- Établir une dépense : le « + » de Financier › Pièces (financier.md §8.3 bis) ---

    def etablir(
        self,
        db: Session,
        membre: Membre,
        *,
        nature: str,
        fichier: tuple[bytes, str, str] | None = None,
        person_id: int | None = None,
        fournisseur: str | None = None,
        jour: date | None = None,
        montant_centimes: int | None = None,
        description: str = "",
        valider: bool = False,
    ) -> NoteFrais:
        """Honoraires ou achat établi par un trésorier : une photo (ou un
        fichier) = une note d'une dépense, créée aussitôt. La lecture remplit
        ce qu'elle peut ; le trésorier vérifie, corrige et valide ensuite
        (rafale). `valider` : tout est saisi, validé en même temps."""
        self._exiger_tresorier(membre)
        if nature not in (HONORAIRES, ACHAT):
            raise ValueError("Une note de frais s'établit au nom de la personne (« Pour qui ? »).")
        lu = {}
        if fichier is not None:
            contenu, nom, type_mime = fichier
            if type_mime not in TYPES_ACCEPTES:
                raise ValueError("Seules les photos (JPEG, PNG, WebP, HEIC) et les PDF sont acceptés.")
            if len(contenu) <= 10 * 1024 * 1024 and self.lecture_disponible:
                try:
                    lu = self.lire_ticket(db, membre, contenu, type_mime)
                except LectureImpossible:
                    lu = {}
        if jour is None and lu.get("date"):
            jour = date.fromisoformat(lu["date"])
        jour = jour or date.today()
        montant = montant_centimes if montant_centimes is not None else (lu.get("montant_centimes") or 0)
        if montant or valider:
            self._valider_saisie(montant, jour)
        description = " ".join((description or lu.get("description") or "").split())[:200]
        note = NoteFrais(org_id=membre.org_id, nature=nature, statut=ENVOYEE, titre="")
        if nature == ACHAT:
            note.person_id = membre.person_id
            note.supplier = " ".join((fournisseur or lu.get("commercant") or "").split())[:120] or None
        else:
            note.person_id = person_id if person_id is not None else self._reconnaitre_prof(db, membre, lu)
            if note.person_id != PERSONNE_A_CHOISIR:
                self._personne_de_l_org(db, membre, note.person_id)
        note.titre = self._titre(note, jour)
        self._recopier_rib(db, note)
        if valider:
            note.statut, note.traitee_le, note.traitee_par = VALIDEE, _maintenant(), membre.person_id
        db.add(note)
        db.flush()
        depense = Depense(
            org_id=membre.org_id, person_id=note.person_id, date=jour, montant_centimes=montant,
            description=description, lue_par_ia=bool(lu), note_id=note.id,
        )
        db.add(depense)
        db.flush()
        if valider:
            self._exiger_complete(note)
        if fichier is not None:
            self._poser_piece(membre, depense, io.BytesIO(fichier[0]), fichier[1], fichier[2])
        db.commit()
        db.refresh(note)
        self._ranger(db, membre, note)
        return note

    def ajouter_page(self, db: Session, membre: Membre, note_id: int, flux: BinaryIO, nom: str, type_mime: str) -> NoteFrais:
        """« Encore une page de celle-ci » : une page de plus pour la dernière
        dépense de la note (facture de deux pages, ticket de dépôt + cahier)."""
        self._exiger_tresorier(membre)
        note = self._note(db, membre.org_id, note_id)
        if note.statut in (REFUSEE, REMBOURSEE) or not note.depenses:
            raise ValueError("On n'ajoute plus de page à cette pièce.")
        if type_mime not in TYPES_ACCEPTES:
            raise ValueError("Seules les photos (JPEG, PNG, WebP, HEIC) et les PDF sont acceptés.")
        depense = note.depenses[-1]
        if len(depense.pieces) >= PIECES_MAX:
            raise ValueError(f"Pas plus de {PIECES_MAX} justificatifs par dépense.")
        self._poser_piece(membre, depense, flux, nom, type_mime)
        db.commit()
        db.refresh(note)
        self._ranger(db, membre, note)
        return note

    def corriger(self, db: Session, membre: Membre, note_id: int, **champs) -> NoteFrais:
        """Vérifier ou compléter ce que la lecture a rempli (honoraires,
        achat), tant que ce n'est pas payé. Une note de frais, elle, se
        corrige par son auteur (reprendre)."""
        self._exiger_tresorier(membre)
        note = self._note(db, membre.org_id, note_id)
        if note.nature == FRAIS:
            raise ValueError("Une note de frais se corrige par son auteur : refusez-la avec un motif.")
        if note.statut not in (ENVOYEE, VALIDEE):
            raise ValueError("Cette pièce n'est plus modifiable.")
        if note.nature == HONORAIRES and champs.get("person_id") is not None and champs["person_id"] != note.person_id:
            self._personne_de_l_org(db, membre, champs["person_id"])
            note.person_id = champs["person_id"]
            for depense in note.depenses:
                depense.person_id = note.person_id
            note.rib_titulaire = note.rib_iban = note.rib_bic = None
            self._recopier_rib(db, note)
        if note.nature == ACHAT and champs.get("fournisseur") is not None:
            note.supplier = " ".join(champs["fournisseur"].split())[:120] or None
        if len(note.depenses) == 1:
            depense = note.depenses[0]
            if champs.get("jour") is not None:
                depense.date = champs["jour"]
            if champs.get("montant_centimes") is not None:
                depense.montant_centimes = champs["montant_centimes"]
            if champs.get("description") is not None:
                depense.description = " ".join(champs["description"].split())[:200]
            self._valider_saisie(depense.montant_centimes, depense.date)
        if champs.get("titre"):
            note.titre = " ".join(champs["titre"].split())[:120]
        elif note.depenses:
            note.titre = self._titre(note, note.depenses[0].date)
        db.commit()
        db.refresh(note)
        self._reranger(db, membre, note)
        self._ranger(db, membre, note)
        return note

    def _reranger(self, db: Session, membre: Membre, note: NoteFrais) -> None:
        """Après une correction (date, personne, fournisseur, montant) : les
        justificatifs déjà rangés vont dans le dossier et sous le nom qu'ils
        auraient eus, saison comprise. Un échec n'annule pas la correction."""
        chemin = self._chemin_docs(db, note)
        rangees = [(d, p) for d in note.depenses for p in d.pieces if p.doc_node_id]
        if self.ports.classeur is None or chemin is None or not rangees:
            return
        try:
            self.ports.classeur.deplacer(
                db, membre, chemin, [(p.doc_node_id, self._nom_dans_docs(note, d, p)) for d, p in rangees],
                le=self._date_docs(note),
            )
        except Exception:
            db.rollback()
            logger.exception("Note de frais %s : justificatifs non déplacés dans les documents", note.id)

    def supprimer_note(self, db: Session, membre: Membre, note_id: int) -> None:
        """Une pièce établie par erreur (photo ratée, doublon), pas encore
        validée : elle et ses justificatifs partent à la corbeille."""
        self._exiger_tresorier(membre)
        note = self._note(db, membre.org_id, note_id)
        if note.nature == FRAIS or note.statut != ENVOYEE:
            raise ValueError("Seule une pièce encore à valider se supprime.")
        rangees = [p.doc_node_id for d in note.depenses for p in d.pieces if p.doc_node_id]
        sur_disque = [p.chemin for d in note.depenses for p in d.pieces if p.doc_node_id is None]
        if rangees:
            self._declasser(db, membre, note, rangees)
        for depense in list(note.depenses):
            db.delete(depense)
        db.delete(note)
        db.commit()
        for chemin in sur_disque:
            self.stockage.delete(membre.org_id, chemin)

    def _personne_de_l_org(self, db: Session, membre: Membre, person_id: int) -> Personne:
        personne = self.ports.annuaire.personnes(db, membre.org_id, {person_id}).get(person_id)
        if personne is None:
            raise LookupError("Personne inconnue dans cette organisation.")
        return personne

    def _reconnaitre_prof(self, db: Session, membre: Membre, lu: dict) -> int:
        """Le nom lu sur une note d'honoraires rapproché d'une fiche ; en cas
        de doute, « Pour qui ? » (PERSONNE_A_CHOISIR)."""
        texte = _sans_accents(f"{lu.get('commercant') or ''} {lu.get('description') or ''}")
        if not texte.strip():
            return PERSONNE_A_CHOISIR
        mots = set(re.findall(r"[a-z]+", texte))
        trouvees = [
            p for p in self.ports.annuaire.toutes(db, membre.org_id)
            if (noms := [m for m in re.findall(r"[a-z]+", _sans_accents(p.nom)) if len(m) > 1]) and all(m in mots for m in noms)
        ]
        return trouvees[0].person_id if len(trouvees) == 1 else PERSONNE_A_CHOISIR

    @staticmethod
    def _titre(note: NoteFrais, jour: date) -> str:
        if note.nature == HONORAIRES:
            return f"Honoraires {MOIS[jour.month - 1]} {jour.year}"
        if note.nature == ACHAT:
            return note.supplier or "Achat"
        return note.titre

    def _recopier_rib(self, db: Session, note: NoteFrais) -> None:
        """Le RIB à payer, s'il est connu : celui de la personne (honoraires),
        ou celui du dernier achat chez ce fournisseur."""
        if note.rib_iban or note.don:
            return
        if note.nature == ACHAT:
            if not note.supplier:
                return
            precedent = db.scalars(
                select(NoteFrais).where(
                    NoteFrais.org_id == note.org_id, NoteFrais.nature == ACHAT, NoteFrais.supplier == note.supplier,
                    NoteFrais.rib_iban.is_not(None),
                ).order_by(NoteFrais.id.desc())
            ).first()
            if precedent is not None:
                note.rib_titulaire, note.rib_iban, note.rib_bic = precedent.rib_titulaire, precedent.rib_iban, precedent.rib_bic
            return
        rib = self.rib(db, note.org_id, note.person_id)
        if rib is not None:
            note.rib_titulaire, note.rib_iban, note.rib_bic = rib.titulaire, rib.iban, rib.bic

    def _poser_piece(self, membre: Membre, depense: Depense, flux: BinaryIO, nom: str, type_mime: str) -> None:
        """Le fichier attend sur le disque d'être rangé dans Docs (_ranger)."""
        extension = Path(nom or "").suffix.lower() or _EXTENSIONS.get(type_mime, "")
        nom_fichier = f"{depense.date.isoformat()} {depense.description or 'ticket'} {depense.id}-{len(depense.pieces) + 1}{extension}"
        dossier = self.stockage.dossier_depenses(membre.org_id, depense.person_id, "")
        chemin, taille = self.stockage.put(membre.org_id, dossier, nom_fichier, flux)
        depense.pieces.append(PieceJustificative(
            chemin=chemin, type_mime=type_mime, nom=(nom or "")[:200], taille=taille, ordre=len(depense.pieces),
        ))

    # --- Rangement dans Docs (§7 bis, financier.md §8.3 bis) ---

    def _chemin_docs(self, db: Session, note: NoteFrais) -> list[str] | None:
        """Dossiers sous Financier (Seb, 30/10) : ACHATS › mois de la pièce
        (« 08.2026 ») ; HONORAIRES › PRENOM NOM du prof › la note ; Notes de
        frais › personne › la note. None : pas encore rangeable (honoraires
        dont on ne sait pas encore pour qui)."""
        if note.nature == ACHAT:
            return [DOSSIERS[ACHAT], f"{self._date_docs(note):%m.%Y}"]
        if note.person_id == PERSONNE_A_CHOISIR:
            return None
        personne = self.ports.annuaire.personnes(db, note.org_id, {note.person_id}).get(note.person_id)
        if note.nature == HONORAIRES:
            return [
                DOSSIERS[HONORAIRES],
                nom_dossier(personne.nom if personne else "?"),
                f"{note.envoyee_le.date().isoformat()} {nom_propre(note.titre)} ({note.id})",
            ]
        return [
            DOSSIERS[note.nature],
            self.stockage.dossier_personne(note.org_id, note.person_id, personne.nom if personne else "?"),
            f"{note.envoyee_le.date().isoformat()} {nom_propre(note.titre)} ({note.id})",
        ]

    @staticmethod
    def _date_docs(note: NoteFrais) -> date:
        """La date qui choisit la saison où ranger : celle de la pièce (la
        première dépense), pas celle du paiement ; une charge appartient à
        l'exercice de sa facture."""
        return min((d.date for d in note.depenses), default=note.envoyee_le.date())

    def _nom_dans_docs(self, note: NoteFrais, depense: Depense, piece: PieceJustificative) -> str:
        """Achats : « 2025-02-09 Amazon 39,90.jpg » ; ailleurs, le nom du disque."""
        if note.nature != ACHAT:
            return Path(piece.chemin).name
        extension = Path(piece.chemin).suffix
        return nom_propre(f"{depense.date.isoformat()} {note.supplier or 'Achat'} {montant_court(depense.montant_centimes)}", 100) + extension

    def _ranger(self, db: Session, membre: Membre, note: NoteFrais) -> None:
        """Range dans Docs les justificatifs de la note encore sur le disque,
        puis les retire du disque : un seul endroit, qui ne bouge plus. Un
        échec n'annule pas l'action : les fichiers restent sur le disque."""
        classeur = self.ports.classeur
        chemin = self._chemin_docs(db, note)
        a_ranger = [(d, p) for d in note.depenses for p in d.pieces if p.doc_node_id is None]
        if classeur is None or chemin is None or not a_ranger:
            return
        fichiers = [(self._nom_dans_docs(note, d, p), self.stockage.chemin(note.org_id, p.chemin)) for d, p in a_ranger]
        try:
            ids = classeur.classer(db, membre, chemin, fichiers, le=self._date_docs(note))
        except Exception:
            db.rollback()
            logger.exception("Note de frais %s : rangement dans les documents impossible", note.id)
            return
        if len(ids) != len(a_ranger):
            return
        anciens = []
        for (_, piece), (nom, _), node_id in zip(a_ranger, fichiers, ids):
            anciens.append(piece.chemin)
            piece.doc_node_id, piece.chemin = node_id, nom
        db.commit()
        for ancien in anciens:
            self.stockage.delete(note.org_id, ancien)

    def _declasser(self, db: Session, membre: Membre, note: NoteFrais, node_ids: list[int]) -> None:
        """Note reprise ou supprimée : son dossier (ou, dans Achats, ses
        fichiers) part à la corbeille des documents."""
        chemin = self._chemin_docs(db, note)
        if self.ports.classeur is None or chemin is None:
            return
        try:
            self.ports.classeur.retirer(db, membre, chemin, node_ids if note.nature == ACHAT else (), le=self._date_docs(note))
        except Exception:
            db.rollback()
            logger.exception("Note de frais %s : retrait des documents impossible", note.id)

    def _recapitulatif(self, db: Session, membre: Membre, note: NoteFrais) -> bytes | None:
        """Le PDF récapitulatif de la note. Un échec ne bloque rien."""
        try:
            ids = {note.person_id} | {i for i in (note.traitee_par, note.remboursee_par) if i}
            personnes = self.ports.annuaire.personnes(db, note.org_id, ids - {PERSONNE_A_CHOISIR})
            nom = lambda i: personnes[i].nom if i in personnes else None  # noqa: E731
            pieces = {
                d.id: [recapitulatif.Piece(p.nom or Path(p.chemin).name, self._chemin_piece(db, membre, p), p.type_mime) for p in d.pieces]
                for d in note.depenses
            }
            return recapitulatif.generer(
                organisation=self.ports.annuaire.organisation(db, note.org_id).nom,
                note=note,
                auteur=(note.supplier if note.nature == ACHAT else nom(note.person_id)) or "?",
                traitee_par=nom(note.traitee_par) if note.traitee_par else None,
                remboursee_par=nom(note.remboursee_par) if note.remboursee_par else None,
                statut=self.libelle_statut(note),
                pieces_par_depense=pieces,
            )
        except Exception:
            logger.exception("Note de frais %s : récapitulatif PDF impossible", note.id)
            return None

    def _ranger_recapitulatif(self, db: Session, membre: Membre, note: NoteFrais) -> None:
        """Le PDF est fait une seule fois, quand c'est payé (financier.md
        §8.3 bis), et rangé à côté des justificatifs."""
        chemin = self._chemin_docs(db, note)
        contenu = self._recapitulatif(db, membre, note)
        if self.ports.classeur is None or chemin is None or contenu is None:
            return
        nom = recapitulatif.NOM_FICHIER if note.nature != ACHAT else f"{nom_propre(note.titre)} ({note.id}).pdf"
        dossier = self.stockage.dossier_depenses(note.org_id, note.person_id, "")
        relatif = self.stockage.ecrire(note.org_id, dossier, nom, contenu)
        try:
            self.ports.classeur.classer(
                db, membre, chemin, [(nom, self.stockage.chemin(note.org_id, relatif))], remplacer={nom}, le=self._date_docs(note)
            )
        except Exception:
            db.rollback()
            logger.exception("Note de frais %s : PDF non rangé dans les documents", note.id)
        finally:
            self.stockage.delete(note.org_id, relatif)

    def refuser(self, db: Session, membre: Membre, note_id: int, motif: str) -> NoteFrais:
        self._exiger_tresorier(membre)
        motif = (motif or "").strip()
        if not motif:
            raise ValueError("Indiquez pourquoi la note est refusée.")
        note = self._note(db, membre.org_id, note_id)
        if note.statut != ENVOYEE:
            raise ValueError("Cette note n'est plus à valider.")
        note.statut, note.motif_refus = REFUSEE, motif[:2000]
        note.traitee_le, note.traitee_par = _maintenant(), membre.person_id
        db.commit()
        db.refresh(note)
        if note.nature == FRAIS:
            self._prevenir_auteur(
                db, membre, note, "refusée",
                f"Votre note de frais a été refusée. Motif : {motif}\nVous pouvez la reprendre pour la corriger et la renvoyer.",
            )
        return note

    def rembourser(self, db: Session, membre: Membre, note_ids: list[int]) -> list[NoteFrais]:
        """Payé sans voir l'opération sur le compte (avant les Virements,
        financier.md §8.3 bis ; gardé pour l'assistant et les anciens écrans)."""
        self._exiger_tresorier(membre)
        notes = [self._note(db, membre.org_id, i) for i in dict.fromkeys(note_ids)]
        if not notes:
            raise ValueError("Cochez au moins une note.")
        for note in notes:
            if note.statut not in EN_PAIEMENT or note.don:
                raise ValueError(f"« {note.titre} » n'est pas à rembourser.")
        for note in notes:
            note.statut, note.remboursee_le, note.remboursee_par = REMBOURSEE, _maintenant(), membre.person_id
        db.commit()
        for note in notes:
            db.refresh(note)
            self._apres_paiement(db, membre, note)
        return notes

    def _apres_paiement(self, db: Session, membre: Membre, note: NoteFrais) -> None:
        self._ranger_recapitulatif(db, membre, note)
        # Celle qui a préparé le virement est prévenue qu'il est passé.
        if note.prepared_by and note.prepared_by != membre.person_id:
            prepare = self.ports.annuaire.personnes(db, note.org_id, {note.prepared_by}).get(note.prepared_by)
            if prepare is not None and prepare.notification_id is not None:
                self._notifier(db, prepare.notification_id, "Payé", f"{self.beneficiaire(db, note)}, {euros(self.total(note))}")
        if note.nature == HONORAIRES and note.person_id != PERSONNE_A_CHOISIR:
            prof = self.ports.annuaire.personnes(db, note.org_id, {note.person_id}).get(note.person_id)
            if prof is not None and prof.notification_id is not None:
                self._notifier(db, prof.notification_id, "Honoraires payés", f"« {note.titre} » : {euros(self.total(note))} par virement.")
        if note.nature == FRAIS:
            self._prevenir_auteur(
                db, membre, note, "remboursée",
                f"Votre note de frais a été remboursée : {euros(self.total(note))} par virement.",
            )

    # --- Virements (financier.md §8.3 bis) : l'appli ne paie pas, elle aide ---

    def payeurs(self, db: Session, membre: Membre) -> list[Personne]:
        """Réglage « Qui paie » ; personne de choisi : les trésoriers."""
        self._exiger_tresorier(membre)
        ids = set(db.scalars(select(Payer.person_id).where(Payer.org_id == membre.org_id)))
        if not ids:
            return self.ports.annuaire.tresoriers(db, membre.org_id)
        return sorted(self.ports.annuaire.personnes(db, membre.org_id, ids).values(), key=lambda p: p.nom.casefold())

    def definir_payeurs(self, db: Session, membre: Membre, person_ids: list[int]) -> list[Personne]:
        self._exiger_tresorier(membre)
        ids = set(person_ids)
        connues = self.ports.annuaire.personnes(db, membre.org_id, ids)
        if ids - connues.keys():
            raise LookupError("Personne inconnue dans cette organisation.")
        for ancien in db.scalars(select(Payer).where(Payer.org_id == membre.org_id)):
            db.delete(ancien)
        for person_id in ids:
            db.add(Payer(org_id=membre.org_id, person_id=person_id))
        db.commit()
        return self.payeurs(db, membre)

    def definir_rib_note(self, db: Session, membre: Membre, note_id: int, *, titulaire: str | None, iban: str | None, bic: str | None) -> NoteFrais:
        """RIB à payer, saisi ou corrigé par un trésorier ; celui d'une personne
        est aussi gardé sur sa fiche (Profil › Mon RIB)."""
        self._exiger_tresorier(membre)
        note = self._note(db, membre.org_id, note_id)
        if note.don or note.statut not in (ENVOYEE, VALIDEE, PREPAREE):
            raise ValueError("Ce virement n'est plus à préparer.")
        iban = normaliser_iban(iban)
        if iban is None:
            raise ValueError("Indiquez l'IBAN.")
        note.rib_iban, note.rib_bic = iban, normaliser_bic(bic)
        note.rib_titulaire = " ".join((titulaire or "").split())[:120] or None
        if note.nature != ACHAT and note.person_id != PERSONNE_A_CHOISIR:
            personne = self._personne_de_l_org(db, membre, note.person_id)
            self.definir_rib(
                db, replace(membre, person_id=personne.person_id, nom=personne.nom),
                titulaire=note.rib_titulaire, iban=iban, bic=note.rib_bic,
            )
        db.commit()
        db.refresh(note)
        return note

    def _a_virer(self, db: Session, membre: Membre, note_id: int, etats: tuple[str, ...]) -> NoteFrais:
        self._exiger_tresorier(membre)
        note = self._note(db, membre.org_id, note_id)
        if note.don or note.statut not in etats:
            raise ValueError("Ce virement n'est pas à faire.")
        if not note.rib_iban:
            raise ValueError("Il manque le RIB.")
        return note

    def preparer(self, db: Session, membre: Membre, note_id: int, payeur_id: int) -> NoteFrais:
        """« Faire payer par … » : prévenue par une notification qui ouvre
        l'aide au virement."""
        note = self._a_virer(db, membre, note_id, (VALIDEE, PREPAREE))
        payeur = next((p for p in self.payeurs(db, membre) if p.person_id == payeur_id), None)
        if payeur is None:
            raise ValueError("Cette personne n'est pas dans « Qui paie ».")
        note.statut, note.prepared_at, note.prepared_by, note.payer_id = PREPAREE, _maintenant(), membre.person_id, payeur_id
        db.commit()
        db.refresh(note)
        if payeur_id != membre.person_id and payeur.notification_id is not None:
            self._notifier(db, payeur.notification_id, "Virement à faire", f"{self.beneficiaire(db, note)}, {euros(self.total(note))}")
        return note

    def virement_fait(self, db: Session, membre: Membre, note_id: int) -> NoteFrais:
        """« J'ai fait le virement » : Envoyé, jusqu'à ce qu'on le voie sur le compte."""
        note = self._a_virer(db, membre, note_id, (VALIDEE, PREPAREE))
        note.statut, note.transfer_sent_at, note.transfer_sent_by = VIREE, _maintenant(), membre.person_id
        db.commit()
        db.refresh(note)
        return note

    def beneficiaire(self, db: Session, note: NoteFrais) -> str:
        if note.rib_titulaire:
            return note.rib_titulaire
        if note.nature == ACHAT:
            return note.supplier or "Fournisseur"
        personne = self.ports.annuaire.personnes(db, note.org_id, {note.person_id}).get(note.person_id)
        return personne.nom if personne else "?"

    def libelle_virement(self, db: Session, note: NoteFrais) -> str:
        """Libellé proposé dans l'aide au virement (« Contretemps honoraires oct 2026 »)."""
        org = self.ports.annuaire.organisation(db, note.org_id).nom
        jour = note.depenses[0].date if note.depenses else note.envoyee_le.date()
        mois = f"{MOIS_COURTS[jour.month - 1]} {jour.year}"
        quoi = {FRAIS: "note de frais", HONORAIRES: "honoraires", ACHAT: f"facture {note.supplier or ''}".strip()}[note.nature]
        # Sans accents : le libellé d'un virement SEPA n'en prend pas partout.
        texte = "".join(c for c in unicodedata.normalize("NFD", f"{org} {quoi} {mois}") if not unicodedata.combining(c))
        return " ".join(texte.split())[:140]

    def virements(self, db: Session, membre: Membre) -> list[dict]:
        """Puce Virements : à payer, préparés, envoyés, et payés depuis moins
        de 60 jours ; toutes natures."""
        self._exiger_tresorier(membre)
        depuis = _maintenant() - timedelta(days=60)
        notes = list(db.scalars(
            select(NoteFrais).where(
                NoteFrais.org_id == membre.org_id, NoteFrais.don.is_(False),
                NoteFrais.statut.in_(EN_PAIEMENT) | ((NoteFrais.statut == REMBOURSEE) & (NoteFrais.remboursee_le >= depuis)),
            ).order_by(NoteFrais.traitee_le, NoteFrais.id)
        ))
        resultat = self.notes_dicts(db, membre, notes)
        for note, ligne in zip(notes, resultat):
            ligne["beneficiaire"] = self.beneficiaire(db, note)
            ligne["libelle_virement"] = self.libelle_virement(db, note)
        return resultat

    # --- Vu sur le compte (financier.md §8.3 bis, rapprochement) ---

    def _operations_prises(self, db: Session, org_id: int) -> set[int]:
        return set(db.scalars(
            select(NoteFrais.bank_operation_id).where(NoteFrais.org_id == org_id, NoteFrais.bank_operation_id.is_not(None))
        ))

    def paiement_propose(self, db: Session, note: NoteFrais, prises: set[int]) -> OperationBancaire | None:
        """Le débit du même montant, après l'envoi du virement (ou autour de la
        date de la dépense : achat payé par carte, virement fait avant la
        facture), de préférence au nom du bénéficiaire. Proposé, jamais
        rattaché sans confirmation."""
        banque, total = self.ports.banque, self.total(note)
        if banque is None or total <= 0 or note.don or note.statut not in (ENVOYEE,) + EN_PAIEMENT:
            return None
        if note.statut == VIREE and note.transfer_sent_at is not None:
            reference = note.transfer_sent_at.date()
            depuis = reference - timedelta(days=3)
        else:
            reference = min((d.date for d in note.depenses), default=note.envoyee_le.date())
            depuis = reference - timedelta(days=45)
        candidates = [o for o in banque.debits(db, note.org_id, total, depuis) if o.id not in prises]
        if not candidates:
            return None
        noms = {m for m in re.findall(r"[a-z]{3,}", _sans_accents(f"{self.beneficiaire(db, note)} {note.supplier or ''}"))}
        return min(
            candidates,
            key=lambda o: (not noms & set(re.findall(r"[a-z]{3,}", _sans_accents(o.libelle))), abs((o.date - reference).days)),
        )

    def payer(self, db: Session, membre: Membre, note_id: int, operation_id: int) -> NoteFrais:
        """Confirmer l'opération vue sur le compte : la pièce y est rattachée
        et passe Payé (aussi tout droit depuis À valider : déjà payé)."""
        self._exiger_tresorier(membre)
        note = self._note(db, membre.org_id, note_id)
        if note.don or note.statut not in (ENVOYEE,) + EN_PAIEMENT:
            raise ValueError("Cette pièce n'est pas à payer.")
        operation = self.ports.banque.operation(db, membre.org_id, operation_id) if self.ports.banque else None
        if operation is None:
            raise LookupError("Opération introuvable sur les comptes.")
        if operation.montant_centimes != -self.total(note):
            raise ValueError("Le montant de l'opération n'est pas celui de la pièce.")
        if operation_id in self._operations_prises(db, membre.org_id):
            raise ValueError("Cette opération est déjà rattachée à une autre pièce.")
        if note.statut == ENVOYEE:
            self._exiger_complete(note)
            note.traitee_le, note.traitee_par = _maintenant(), membre.person_id
        note.statut, note.remboursee_le, note.remboursee_par = REMBOURSEE, _maintenant(), membre.person_id
        note.bank_operation_id = operation_id
        db.commit()
        db.refresh(note)
        self._apres_paiement(db, membre, note)
        return note

    def lignes_export(self, db: Session, membre: Membre, debut: date | None, fin: date | None, nature: str = FRAIS) -> list[dict]:
        """Une ligne par dépense des notes de cette nature (§7), pour Excel."""
        self._exiger_tresorier(membre)
        notes = list(db.scalars(
            select(NoteFrais).where(NoteFrais.org_id == membre.org_id, NoteFrais.nature == nature).order_by(NoteFrais.envoyee_le)
        ))
        personnes = self.ports.annuaire.personnes(db, membre.org_id, {n.person_id for n in notes} - {PERSONNE_A_CHOISIR})
        lignes = []
        for note in notes:
            for depense in note.depenses:
                if (debut and depense.date < debut) or (fin and depense.date > fin):
                    continue
                personne = personnes.get(note.person_id)
                lignes.append({
                    "date": depense.date,
                    "personne": (note.supplier or "") if note.nature == ACHAT else (personne.nom if personne else ""),
                    "categorie": depense.categorie.libelle if depense.categorie else "",
                    "description": depense.description,
                    "montant": depense.montant_centimes / 100,
                    "justificatif": "oui" if depense.pieces else "non",
                    "note": note.titre,
                    "statut": self.libelle_statut(note),
                    "envoyee_le": note.envoyee_le.date(),
                })
        return lignes

    # --- Présentation ---

    @staticmethod
    def total(note: NoteFrais) -> int:
        return sum(d.montant_centimes for d in note.depenses)

    @staticmethod
    def libelle_statut(note: NoteFrais) -> str:
        """Côté membre (§5) ; Financier › Pièces a ses propres badges."""
        if note.statut == VALIDEE and note.don:
            return "Don validé"
        return {
            ENVOYEE: "En attente", VALIDEE: "Validée", REFUSEE: "Refusée", PREPAREE: "Validée",
            VIREE: "Virement envoyé", REMBOURSEE: "Remboursée",
        }[note.statut]

    @staticmethod
    def depense_dict(depense: Depense) -> dict:
        return {
            "id": depense.id,
            "date": depense.date.isoformat(),
            "montant_centimes": depense.montant_centimes,
            "categorie": {"id": depense.categorie.id, "libelle": depense.categorie.libelle} if depense.categorie else None,
            "description": depense.description,
            "sans_justificatif": not depense.pieces,
            "lue_par_ia": depense.lue_par_ia,
            "pieces": [{"id": p.id, "type_mime": p.type_mime, "nom": p.nom} for p in depense.pieces],
        }

    @staticmethod
    def rib_dict(rib: Rib | None) -> dict | None:
        if rib is None:
            return None
        return {"titulaire": rib.titulaire, "iban": rib.iban, "bic": rib.bic}

    def note_dict(self, note: NoteFrais, *, personnes: dict[int, Personne] | None = None) -> dict:
        resultat = {
            "id": note.id,
            "titre": note.titre,
            "nature": note.nature,
            "fournisseur": note.supplier,
            "statut": note.statut,
            "libelle_statut": self.libelle_statut(note),
            "don": note.don,
            "total_centimes": self.total(note),
            "envoyee_le": note.envoyee_le.isoformat(),
            "traitee_le": note.traitee_le.isoformat() if note.traitee_le else None,
            "remboursee_le": note.remboursee_le.isoformat() if note.remboursee_le else None,
            "motif_refus": note.motif_refus,
            "depenses": [self.depense_dict(d) for d in note.depenses],
            "rib": None if note.don or not note.rib_iban else {
                "titulaire": note.rib_titulaire, "iban": note.rib_iban, "bic": note.rib_bic,
            },
        }
        if personnes is not None:
            auteur = personnes.get(note.person_id)
            par = personnes.get(note.traitee_par) if note.traitee_par else None
            resultat["personne"] = (
                None if note.person_id == PERSONNE_A_CHOISIR
                else {"person_id": note.person_id, "nom": auteur.nom if auteur else "?", "role": auteur.role if auteur else ""}
            )
            resultat["traitee_par"] = par.nom if par else None
            for cle, person_id in (("prepare_par", note.prepared_by), ("payeur", note.payer_id)):
                quelqu_un = personnes.get(person_id) if person_id else None
                resultat[cle] = {"person_id": person_id, "nom": quelqu_un.nom} if quelqu_un else None
            resultat["prepare_le"] = note.prepared_at.isoformat() if note.prepared_at else None
            resultat["vire_le"] = note.transfer_sent_at.isoformat() if note.transfer_sent_at else None
        return resultat

    # --- Alertes (§9) ---

    def _prevenir_tresoriers(self, db: Session, membre: Membre, note: NoteFrais) -> None:
        """Mail à l'adresse de trésorerie (sinon à chaque trésorier), sauf
        si l'auteur a lui-même cette adresse : alors aux autres trésoriers.
        Notification dans l'appli : chaque trésorier sauf l'auteur."""
        annuaire = self.ports.annuaire
        org = annuaire.organisation(db, membre.org_id)
        autres = [t for t in annuaire.tresoriers(db, membre.org_id) if t.person_id != membre.person_id]
        siennes = {e.lower() for e in membre.emails}
        if org.email_tresorier and org.email_tresorier.lower() not in siennes:
            destinataires = [org.email_tresorier]
        else:
            destinataires = list(dict.fromkeys(e for t in autres for e in t.emails if e.lower() not in siennes))
        total = euros(self.total(note))
        nb = len(note.depenses)
        resume = f"{membre.nom} : « {note.titre} », {nb} dépense{'s' if nb > 1 else ''}, {total}"
        if note.don:
            resume += " (don à l'association)"
        for tresorier in autres:
            if tresorier.notification_id is not None:
                self._notifier(db, tresorier.notification_id, "Nouvelle note de frais", resume)
        if destinataires:
            lien = f"{org.adresse_web}/"
            texte = (
                f"Bonjour,\n\n{membre.nom} vient d'envoyer une note de frais.\n\n"
                f"{note.titre}\n{nb} dépense{'s' if nb > 1 else ''}, total {total}"
                f"{' (don à l’association)' if note.don else ''}\n\n"
                f"Pour la valider : onglet Financier de l'application {org.nom}.\n{lien}\n\n"
                f"Répondre à ce mail écrit directement à {membre.nom}.\n"
            )
            self._mail(db, membre.org_id, destinataires, f"Note de frais de {membre.nom} : {total}", texte, membre.emails[0] if membre.emails else None)

    def _prevenir_auteur(self, db: Session, tresorier: Membre, note: NoteFrais, etat: str, message: str) -> None:
        annuaire = self.ports.annuaire
        org = annuaire.organisation(db, note.org_id)
        auteur = annuaire.personnes(db, note.org_id, {note.person_id}).get(note.person_id)
        if auteur is None:
            return
        titre = f"Note de frais {etat}"
        if auteur.notification_id is not None:
            self._notifier(db, auteur.notification_id, titre, f"« {note.titre} » : {message.splitlines()[0]}")
        if auteur.emails and auteur.person_id != tresorier.person_id:
            repondre_a = org.email_tresorier or (tresorier.emails[0] if tresorier.emails else None) or org.email_contact
            texte = (
                f"Bonjour {auteur.nom},\n\n{message}\n\n"
                f"Note : {note.titre} ({euros(self.total(note))})\n"
                f"Détail dans l'application {org.nom}, Profil, Mes notes de frais.\n{org.adresse_web}/\n"
            )
            self._mail(db, note.org_id, list(auteur.emails), f"{titre} : {note.titre}", texte, repondre_a)

    def _notifier(self, db: Session, notification_id: int, titre: str, corps: str) -> None:
        try:
            self.ports.notifieur.notifier(db, notification_id, titre, corps)
        except Exception:  # noqa: BLE001 - une alerte ne fait jamais échouer l'action
            logger.exception("Notification de note de frais non envoyée")

    def _mail(self, db: Session, org_id: int, a: list[str], sujet: str, texte: str, repondre_a: str | None) -> None:
        corps_html = "".join(f"<p>{html.escape(p).replace(chr(10), '<br>')}</p>" for p in texte.split("\n\n"))
        try:
            self.ports.messager.envoyer(db, org_id, a, sujet, texte, corps_html, repondre_a)
        except Exception:  # noqa: BLE001
            logger.exception("Mail de note de frais non envoyé")
