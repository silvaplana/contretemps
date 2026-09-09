"""Import Excel réel des élèves (voir spec/SPEC.md §6.4bis). Fichier
SÉPARÉ de eleves.py qui réutilise ses primitives CRUD au lieu de les
dupliquer — ne fait QUE lire le classeur, résoudre les colonnes de cours
et orchestrer les décisions d'import (rien écrit en base avant
validation explicite de l'admin, voir `valider`).
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

from cours import CoursService
from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from .eleves import Eleves
from .models import MappingColonneImport

# En-têtes abrégés connus par défaut, indépendamment de l'école (voir
# §6.4bis : "une correspondance en base de données Python simple suffit,
# pas besoin d'appel IA"). Une colonne absente d'ici passe par
# `mappings_colonnes_import` (mémorisation par école), puis en dernier
# recours par l'alerte à l'admin.
MAPPING_COLONNES_COURS_PAR_DEFAUT: dict[str, str] = {
    "Eveil": "Eveil",
    "Class Ini": "Classique initiation",
    "Jazz Ini": "Jazz initiation",
    "Class Moy": "Classique moyen",
    "Jazz Moy": "Jazz moyen",
    "Jazz Jr": "Jazz junior",
    "Class Inter": "Classique intermédiaire",
    "Jazz Inter": "Jazz intermédiaire",
    "Class Av": "Classique avancé",
    "Jazz Av": "Jazz avancé",
}

COLONNES_FIXES = {
    "Nom",
    "Prénom",
    "Nom-Prénom parent",
    "Email",
    "Adresse",
    "Téléphone",
    "Date de naissance",
}

_RE_NOTATION_SCIENTIFIQUE = re.compile(r"e[+-]?\d", re.IGNORECASE)


@dataclass
class LigneApercu:
    numero_ligne: int
    nom: str
    prenom: str
    email: str | None
    telephone: str | None
    telephone_suspect: bool
    adresse: str | None
    date_naissance: dt.date | None
    contact_parent_brut: str | None
    cours_ids: list[int] = field(default_factory=list)
    colonnes_non_reconnues: list[str] = field(default_factory=list)
    eleve_existant_id: int | None = None
    action: str = "creer"  # 'creer' | 'mettre_a_jour'


@dataclass
class ApercuImport:
    lignes: list[LigneApercu]
    colonnes_non_reconnues_globales: list[str]


def _extraire_date_naissance(valeur) -> dt.date | None:
    """"la partie avant le ' = '" (voir §6.4bis) — le fichier réel combine
    date de naissance et âge calculé à la main ; l'âge écrit est ignoré,
    recalculé à la volée ailleurs (voir eleves.calculer_age)."""
    if valeur is None or valeur == "":
        return None
    if isinstance(valeur, dt.datetime):
        return valeur.date()
    if isinstance(valeur, dt.date):
        return valeur
    brut = str(valeur).split("=")[0].strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(brut, fmt).date()
        except ValueError:
            continue
    return None


def _telephone_texte(valeur) -> tuple[str | None, bool]:
    """Voir §6.4bis : au moins un téléphone du fichier réel est interprété
    par Excel comme un NOMBRE (notation scientifique à l'affichage),
    perdant le zéro initial. Le signal le plus fiable est le type de la
    cellule (nombre au lieu de texte), pas seulement la présence d'un
    "E" dans une représentation textuelle. Renvoie (texte, suspect)."""
    if valeur is None or valeur == "":
        return None, False
    if isinstance(valeur, (int, float)):
        return str(valeur), True
    texte = str(valeur).strip()
    return texte, bool(_RE_NOTATION_SCIENTIFIQUE.search(texte))


def _decouper_nom_prenom_contact(chaine: str) -> tuple[str | None, str | None]:
    """"Nom-Prénom parent" (voir §6.4bis) : premier mot = nom, reste =
    prénom, dans cet ordre littéral de l'en-tête."""
    morceaux = chaine.strip().split(None, 1)
    if not morceaux:
        return None, None
    if len(morceaux) == 1:
        return morceaux[0], None
    return morceaux[0], morceaux[1]


class ImportExcel:
    def __init__(self, eleves: Eleves, cours: CoursService) -> None:
        self.eleves = eleves
        self.cours = cours

    # --- Mémorisation du mapping de colonnes (voir §6.4bis) ---

    def _mapping_memorise(self, db: Session, ecole_id: int) -> dict[str, int]:
        lignes = db.scalars(
            select(MappingColonneImport).where(MappingColonneImport.ecole_id == ecole_id)
        )
        return {m.en_tete_excel: m.cours_id for m in lignes}

    def memoriser_mapping_colonne(
        self, db: Session, ecole_id: int, en_tete_excel: str, cours_id: int
    ) -> MappingColonneImport:
        """Décision humaine mémorisée pour les imports suivants (voir
        §6.4bis) — upsert par (ecole_id, en_tete_excel)."""
        existant = db.scalar(
            select(MappingColonneImport).where(
                MappingColonneImport.ecole_id == ecole_id,
                MappingColonneImport.en_tete_excel == en_tete_excel,
            )
        )
        if existant is None:
            existant = MappingColonneImport(
                ecole_id=ecole_id, en_tete_excel=en_tete_excel, cours_id=cours_id
            )
            db.add(existant)
        else:
            existant.cours_id = cours_id
        db.commit()
        db.refresh(existant)
        return existant

    def resoudre_colonnes_cours(
        self, db: Session, ecole_id: int, en_tetes: list[str]
    ) -> tuple[dict[str, int], list[str]]:
        """(en_tete -> cours_id résolus, en_tetes non reconnues). Ordre de
        résolution : (1) nom de cours exact en base, (2) abréviation
        connue par défaut, (3) mapping mémorisé pour cette école."""
        cours_ecole = {c.nom: c.id for c in self.cours.list(db, ecole_id)}
        memorises = self._mapping_memorise(db, ecole_id)

        resolues: dict[str, int] = {}
        non_reconnues: list[str] = []
        for en_tete in en_tetes:
            if en_tete in cours_ecole:
                resolues[en_tete] = cours_ecole[en_tete]
                continue
            nom_mappe = MAPPING_COLONNES_COURS_PAR_DEFAUT.get(en_tete)
            if nom_mappe and nom_mappe in cours_ecole:
                resolues[en_tete] = cours_ecole[nom_mappe]
                continue
            if en_tete in memorises:
                resolues[en_tete] = memorises[en_tete]
                continue
            non_reconnues.append(en_tete)
        return resolues, non_reconnues

    # --- Lecture du classeur (phase 1 : rien n'est écrit en base) ---

    def previsualiser(self, db: Session, ecole_id: int, fichier) -> ApercuImport:
        """`fichier` : chemin ou objet fichier-binaire (voir openpyxl).
        Voir §6.4bis : "rien n'est écrit en base tant que l'admin n'a pas
        validé l'écran de relecture dans son ensemble"."""
        classeur = load_workbook(fichier, data_only=True)
        feuille = classeur.active
        lignes_brutes = list(feuille.iter_rows(values_only=True))
        entetes = [str(c).strip() if c is not None else "" for c in lignes_brutes[0]]
        index = {nom: i for i, nom in enumerate(entetes)}

        colonnes_cours = [e for e in entetes if e and e not in COLONNES_FIXES]
        resolues, non_reconnues = self.resoudre_colonnes_cours(db, ecole_id, colonnes_cours)

        def valeur(ligne, nom_colonne):
            i = index.get(nom_colonne)
            return ligne[i] if i is not None and i < len(ligne) else None

        lignes: list[LigneApercu] = []
        for numero, ligne in enumerate(lignes_brutes[1:], start=2):
            nom = str(valeur(ligne, "Nom") or "").strip()
            prenom = str(valeur(ligne, "Prénom") or "").strip()
            if not nom and not prenom:
                continue  # ligne vide (ex. fin de fichier)

            brut_email = valeur(ligne, "Email")
            email = str(brut_email).strip() or None if brut_email else None
            telephone, telephone_suspect = _telephone_texte(valeur(ligne, "Téléphone"))
            brut_adresse = valeur(ligne, "Adresse")
            adresse = str(brut_adresse).strip() or None if brut_adresse else None
            date_naissance = _extraire_date_naissance(valeur(ligne, "Date de naissance"))
            brut_contact = valeur(ligne, "Nom-Prénom parent")
            contact_parent_brut = str(brut_contact).strip() if brut_contact else None

            cours_ids = [
                resolues[c] for c in colonnes_cours if c in resolues and valeur(ligne, c)
            ]
            colonnes_non_reconnues_ligne = [
                c for c in colonnes_cours if c in non_reconnues and valeur(ligne, c)
            ]

            eleve_existant_id = self._trouver_doublon(db, ecole_id, nom, prenom, date_naissance)

            lignes.append(
                LigneApercu(
                    numero_ligne=numero,
                    nom=nom,
                    prenom=prenom,
                    email=email,
                    telephone=telephone,
                    telephone_suspect=telephone_suspect,
                    adresse=adresse,
                    date_naissance=date_naissance,
                    contact_parent_brut=contact_parent_brut,
                    cours_ids=cours_ids,
                    colonnes_non_reconnues=colonnes_non_reconnues_ligne,
                    eleve_existant_id=eleve_existant_id,
                    action="mettre_a_jour" if eleve_existant_id else "creer",
                )
            )

        return ApercuImport(
            lignes=lignes, colonnes_non_reconnues_globales=sorted(set(non_reconnues))
        )

    def _trouver_doublon(
        self, db: Session, ecole_id: int, nom: str, prenom: str, date_naissance: dt.date | None
    ) -> int | None:
        """Correspondance (nom, prénom, date_naissance) — voir §6.4bis :
        l'email est volontairement exclu (frères/sœurs qui le partagent)."""
        for existant in self.eleves.comptes.trouver_par_nom_prenom(
            db, ecole_id, nom, prenom, role="eleve"
        ):
            profil = self.eleves.get_profil(db, existant.id)
            if profil is not None and profil.date_naissance == date_naissance:
                return existant.id
        return None

    # --- Écriture en base (phase 2 : après validation admin) ---

    def valider(self, db: Session, ecole_id: int, lignes: list[LigneApercu]) -> dict:
        """`lignes` : celles renvoyées par `previsualiser`, avec `action`
        éventuellement corrigé par l'admin à la relecture (voir §6.4bis :
        choix global par défaut + ajustable ligne par ligne — cet
        ajustement est fait par l'appelant/le futur frontend avant
        d'appeler `valider`, pas ici)."""
        crees = mis_a_jour = ignores = 0
        for ligne in lignes:
            if ligne.action == "ignorer":
                ignores += 1
                continue

            if ligne.action == "mettre_a_jour" and ligne.eleve_existant_id:
                eleve_id = ligne.eleve_existant_id
                self.eleves.comptes.update(db, eleve_id, email=ligne.email, telephone=ligne.telephone)
                self.eleves.update_profil(
                    db, eleve_id, adresse=ligne.adresse, date_naissance=ligne.date_naissance
                )
                mis_a_jour += 1
            else:  # 'creer', ou 'dupliquer' malgré un doublon détecté
                compte, _profil = self.eleves.create(
                    db,
                    ecole_id,
                    nom=ligne.nom,
                    prenom=ligne.prenom,
                    email=ligne.email,
                    telephone=ligne.telephone,
                    date_naissance=ligne.date_naissance,
                    adresse=ligne.adresse,
                )
                eleve_id = compte.id
                crees += 1

            if ligne.contact_parent_brut:
                # "Nom-Prénom parent" (voir §6.4bis) — pas de lien
                # (père/mère) dans le fichier, laissé vide.
                contact_nom, contact_prenom = _decouper_nom_prenom_contact(
                    ligne.contact_parent_brut
                )
                self.eleves.ajouter_contact(
                    db,
                    eleve_id,
                    nom=contact_nom,
                    prenom=contact_prenom,
                    telephone=ligne.telephone,
                    email=ligne.email,
                )

            for cours_id in ligne.cours_ids:
                self.cours.inscrire_eleve(db, cours_id, eleve_id)

        return {"crees": crees, "mis_a_jour": mis_a_jour, "ignores": ignores}
