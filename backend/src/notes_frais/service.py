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
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    ENVOYEE,
    REFUSEE,
    REMBOURSEE,
    VALIDEE,
    CategorieFrais,
    Depense,
    NoteFrais,
    PieceJustificative,
    Rib,
)
from .ports import LectureImpossible, Membre, Personne, Ports, TicketLu
from .stockage import StockageEnveloppes, nom_propre

logger = logging.getLogger(__name__)

TYPES_ACCEPTES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/heic", "image/heif", "application/pdf"}
PIECES_MAX = 5
MONTANT_MAX_CENTIMES = 10_000_000  # 100 000 €, garde-fou contre une virgule oubliée

FILTRES = ("a_valider", "a_rembourser", "terminees")
_EXTENSIONS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif",
               "image/heic": ".heic", "image/heif": ".heif", "application/pdf": ".pdf"}


def _maintenant() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def euros(centimes: int) -> str:
    """12345 -> « 123,45 € » (espace insécable avant les milliers)."""
    entier, reste = divmod(abs(centimes), 100)
    groupe = f"{entier:,}".replace(",", " ")
    return f"{'-' if centimes < 0 else ''}{groupe},{reste:02d} €"


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

    def fichier_piece(self, db: Session, membre: Membre, piece_id: int) -> tuple[Path, str, str]:
        """(chemin, type, nom) : pour la personne elle-même ou un trésorier."""
        piece = db.get(PieceJustificative, piece_id)
        depense = piece.depense if piece is not None else None
        if depense is None or depense.org_id != membre.org_id:
            raise LookupError("Justificatif introuvable.")
        if depense.person_id != membre.person_id and not (membre.est_tresorier or membre.est_superuser):
            raise LookupError("Justificatif introuvable.")
        chemin = self.stockage.chemin(membre.org_id, piece.chemin)
        if not chemin.exists():
            raise LookupError("Fichier du justificatif introuvable.")
        return chemin, piece.type_mime, piece.nom

    def archive_justificatifs(self, db: Session, membre: Membre, note_id: int) -> tuple[bytes, str]:
        """Zip des justificatifs d'une note (§7), pour un trésorier ou
        l'auteur : (contenu, nom du fichier). Noms tels que sur le disque."""
        note = self._note(db, membre.org_id, note_id)
        if note.person_id != membre.person_id and not (membre.est_tresorier or membre.est_superuser):
            raise LookupError("Note de frais introuvable.")
        tampon = io.BytesIO()
        with zipfile.ZipFile(tampon, "w", zipfile.ZIP_STORED) as archive:
            for depense in note.depenses:
                for piece in depense.pieces:
                    chemin = self.stockage.chemin(membre.org_id, piece.chemin)
                    if chemin.exists():
                        archive.write(chemin, chemin.name)
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
        db.add(note)
        db.flush()
        enveloppe = self.stockage.dossier_note(
            membre.org_id, membre.person_id, membre.nom, date.today().isoformat(), titre, note.id
        )
        for depense in depenses:
            depense.note_id = note.id
            for piece in depense.pieces:
                piece.chemin = self.stockage.deplacer(membre.org_id, piece.chemin, enveloppe)
        db.commit()
        db.refresh(note)
        self._prevenir_tresoriers(db, membre, note)
        return note

    def reprendre(self, db: Session, membre: Membre, note_id: int) -> None:
        """Tant qu'aucun trésorier n'a validé (ou après un refus) : la note
        disparaît et ses dépenses repassent « À envoyer »."""
        note = self._note(db, membre.org_id, note_id)
        if note.person_id != membre.person_id:
            raise LookupError("Note de frais introuvable.")
        if note.statut not in (ENVOYEE, REFUSEE):
            raise ValueError("Cette note est déjà validée : elle ne peut plus être reprise.")
        dossier = self.stockage.dossier_depenses(membre.org_id, membre.person_id, membre.nom)
        for depense in list(note.depenses):
            depense.note_id = None
            for piece in depense.pieces:
                piece.chemin = self.stockage.deplacer(membre.org_id, piece.chemin, dossier)
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
                (NoteFrais.statut == ENVOYEE) | ((NoteFrais.statut == VALIDEE) & NoteFrais.don.is_(False)),
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

    def tresorerie(self, db: Session, membre: Membre, filtre: str) -> list[dict]:
        self._exiger_tresorier(membre)
        if filtre not in FILTRES:
            raise ValueError("Filtre inconnu.")
        requete = select(NoteFrais).where(NoteFrais.org_id == membre.org_id)
        if filtre == "a_valider":
            requete = requete.where(NoteFrais.statut == ENVOYEE).order_by(NoteFrais.envoyee_le)
        elif filtre == "a_rembourser":
            requete = requete.where(NoteFrais.statut == VALIDEE, NoteFrais.don.is_(False)).order_by(NoteFrais.traitee_le)
        else:
            requete = requete.where(
                (NoteFrais.statut.in_((REMBOURSEE, REFUSEE))) | ((NoteFrais.statut == VALIDEE) & NoteFrais.don.is_(True))
            ).order_by(NoteFrais.envoyee_le.desc())
        notes = list(db.scalars(requete))
        personnes = self.ports.annuaire.personnes(db, membre.org_id, {n.person_id for n in notes} | {n.traitee_par for n in notes if n.traitee_par})
        return [self.note_dict(n, personnes=personnes) for n in notes]

    def compteurs_tresorerie(self, db: Session, membre: Membre) -> dict:
        self._exiger_tresorier(membre)
        return {filtre: len(self.tresorerie(db, membre, filtre)) for filtre in ("a_valider", "a_rembourser")}

    def valider(self, db: Session, membre: Membre, note_id: int) -> NoteFrais:
        self._exiger_tresorier(membre)
        note = self._note(db, membre.org_id, note_id)
        if note.statut != ENVOYEE:
            raise ValueError("Cette note n'est plus à valider.")
        if note.person_id == membre.person_id and any(
            t.person_id != membre.person_id for t in self.ports.annuaire.tresoriers(db, membre.org_id)
        ):
            raise PermissionError("Un autre trésorier doit valider votre propre note.")
        note.statut, note.traitee_le, note.traitee_par = VALIDEE, _maintenant(), membre.person_id
        db.commit()
        db.refresh(note)
        if note.don:
            self._prevenir_auteur(db, membre, note, "validée (don à l'association)", "Merci pour votre don : votre note de frais a été validée.")
        else:
            self._prevenir_auteur(db, membre, note, "validée", "Votre note de frais a été validée ; le remboursement suivra.")
        return note

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
        self._prevenir_auteur(
            db, membre, note, "refusée",
            f"Votre note de frais a été refusée. Motif : {motif}\nVous pouvez la reprendre pour la corriger et la renvoyer.",
        )
        return note

    def rembourser(self, db: Session, membre: Membre, note_ids: list[int]) -> list[NoteFrais]:
        """Le trésorier a fait les virements depuis la banque (§1)."""
        self._exiger_tresorier(membre)
        notes = [self._note(db, membre.org_id, i) for i in dict.fromkeys(note_ids)]
        if not notes:
            raise ValueError("Cochez au moins une note.")
        for note in notes:
            if note.statut != VALIDEE or note.don:
                raise ValueError(f"« {note.titre} » n'est pas à rembourser.")
        for note in notes:
            note.statut, note.remboursee_le, note.remboursee_par = REMBOURSEE, _maintenant(), membre.person_id
        db.commit()
        for note in notes:
            db.refresh(note)
            self._prevenir_auteur(
                db, membre, note, "remboursée",
                f"Votre note de frais a été remboursée : {euros(self.total(note))} par virement.",
            )
        return notes

    def lignes_export(self, db: Session, membre: Membre, debut: date | None, fin: date | None) -> list[dict]:
        """Une ligne par dépense des notes envoyées (§7), pour Excel."""
        self._exiger_tresorier(membre)
        notes = list(db.scalars(select(NoteFrais).where(NoteFrais.org_id == membre.org_id).order_by(NoteFrais.envoyee_le)))
        personnes = self.ports.annuaire.personnes(db, membre.org_id, {n.person_id for n in notes})
        lignes = []
        for note in notes:
            for depense in note.depenses:
                if (debut and depense.date < debut) or (fin and depense.date > fin):
                    continue
                personne = personnes.get(note.person_id)
                lignes.append({
                    "date": depense.date,
                    "personne": personne.nom if personne else "",
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
        if note.statut == VALIDEE and note.don:
            return "Don validé"
        return {ENVOYEE: "En attente", VALIDEE: "Validée", REFUSEE: "Refusée", REMBOURSEE: "Remboursée"}[note.statut]

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
            resultat["personne"] = {"nom": auteur.nom if auteur else "?", "role": auteur.role if auteur else ""}
            resultat["traitee_par"] = par.nom if par else None
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
