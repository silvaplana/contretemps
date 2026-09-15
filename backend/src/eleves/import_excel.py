"""Import du fichier élèves OFFICIEL (Excel ou CSV, voir spec/SPEC.md
§6.4bis) — Admin > École ("Intégrer fichier élèves officiel") ET Admin >
Élèves (bouton "Importer"), les deux mènent ici (demande utilisateur
explicite). Fichier SÉPARÉ de eleves.py qui réutilise ses primitives CRUD
au lieu de les dupliquer — ne fait QUE lire le fichier, résoudre les
colonnes de cours et calculer les différences avec les élèves déjà en
base (rien écrit avant validation explicite de l'admin, voir `valider`).
"""

from __future__ import annotations

import csv
import datetime as dt
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

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
    "Eveil": "Éveil",
    "Class Ini": "Class Ini",
    "Jazz Ini": "Jazz Ini",
    "Class Moy": "Class Moy",
    "Jazz Moy": "Jazz Moy",
    "Jazz Jr": "Jazz Junior",
    "Class Inter": "Class Inter",
    "Jazz Inter": "Jazz Inter",
    "Class Av": "Class AV",
    "Jazz Av": "Jazz AV",
}

_RE_NOTATION_SCIENTIFIQUE = re.compile(r"e[+-]?\d", re.IGNORECASE)


def _normaliser(texte: str) -> str:
    """minuscules, sans accents, lettres/chiffres seulement — pour
    comparer un en-tête de colonne malgré des variantes de libellé ("Nom
    adhérent" vs "Nom", "E-Mail" vs "Email", "Nom - Prénom parent" vs
    "Nom-Prénom parent"...). Volontairement simple/déterministe (voir
    §6.4bis : "pas besoin d'appel IA" — même raisonnement ici)."""
    sans_accents = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", sans_accents.lower())


def _ressemble(en_tete: str, *motifs: str) -> bool:
    normalise = _normaliser(en_tete)
    return any(motif in normalise for motif in motifs)


def _trouver_colonne(entetes: list[str], deja_pris: set[int], *motifs: str) -> int | None:
    for i, e in enumerate(entetes):
        if i in deja_pris or not e:
            continue
        if _ressemble(e, *motifs):
            return i
    return None


@dataclass
class DifferenceChamp:
    """Une différence entre la fiche actuelle et le fichier, pour un
    élève déjà existant — présentée à l'admin qui choisit, champ par
    champ (demande utilisateur explicite), plutôt que l'ancien
    comportement qui écrasait tout silencieusement."""

    champ: str  # 'email' | 'telephone' | 'adresse' | 'date_naissance' | 'cours'
    valeur_actuelle: Any
    valeur_fichier: Any


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
    # Nouvel élève : tous les cours marqués dans le fichier. Élève
    # existant : uniquement les cours marqués qu'il n'a PAS déjà (jamais
    # de désinscription automatique, voir _differences) — non vide
    # seulement s'il y a une différence "cours" à proposer.
    cours_ids: list[int] = field(default_factory=list)
    colonnes_non_reconnues: list[str] = field(default_factory=list)
    eleve_existant_id: int | None = None
    # Vide pour un nouvel élève, ou pour un élève existant déjà à jour.
    differences: list[DifferenceChamp] = field(default_factory=list)
    # Plusieurs élèves existants portent déjà ce nom/prénom, sans date de
    # naissance pour départager (voir _trouver_eleve_existant) — jamais
    # créé automatiquement (risque de doublon), `creer` à False par
    # défaut : l'admin doit consciemment cocher pour forcer la création.
    ambigu: bool = False
    # Nouvel élève seulement : décochable par l'admin avant validation
    # (ex. ligne parasite du fichier) — sans objet si eleve_existant_id.
    creer: bool = True
    # Plusieurs lignes du FICHIER partagent ce nom/prénom (voir
    # previsualiser) — jamais fusionnées ni choisies automatiquement
    # (demande utilisateur explicite), juste signalées et décochées par
    # défaut : à l'admin de cocher celle(s) à garder.
    doublon_fichier: bool = False
    # Élève existant seulement : quels `differences[].champ` l'admin a
    # choisi d'appliquer ("utiliser le fichier") — les autres restent
    # inchangés (choix par défaut sûr : ne jamais écraser sans decision
    # explicite, contrairement à l'ancien comportement).
    champs_a_appliquer: list[str] = field(default_factory=list)


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


def _lire_lignes_brutes(nom_fichier: str, fichier) -> list[list]:
    """CSV ou Excel (1er onglet SEULEMENT — contrainte annoncée à
    l'utilisateur, voir receiver.py) -> lignes brutes uniformes, en-têtes
    compris en 1re ligne."""
    nom_lower = (nom_fichier or "").lower()
    if nom_lower.endswith(".csv"):
        contenu = fichier.read()
        if isinstance(contenu, bytes):
            contenu = contenu.decode("utf-8-sig")  # -sig : tolère un BOM (Excel Windows)
        try:
            dialecte = csv.Sniffer().sniff(contenu[:2048], delimiters=",;")
        except csv.Error:
            dialecte = csv.excel  # repli : virgule (voir csv.excel)
        return [
            [cellule if cellule != "" else None for cellule in ligne]
            for ligne in csv.reader(contenu.splitlines(), dialecte)
        ]
    if nom_lower.endswith(".xlsx"):
        classeur = load_workbook(fichier, data_only=True)
        feuille = classeur.active  # "1er onglet" — la contrainte annoncée
        return [list(ligne) for ligne in feuille.iter_rows(values_only=True)]
    raise ValueError("Le fichier doit être un .csv, ou un .xlsx (Excel, 1er onglet).")


class ImportExcel:
    def __init__(self, eleves: Eleves, cours: CoursService) -> None:
        self.eleves = eleves
        self.cours = cours

    # --- Mémorisation du mapping de colonnes de cours (voir §6.4bis) ---

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

    # --- Lecture du fichier (phase 1 : rien n'est écrit en base) ---

    def previsualiser(self, db: Session, ecole_id: int, fichier, nom_fichier: str) -> ApercuImport:
        """`fichier` : objet fichier-binaire. `nom_fichier` : nom
        d'origine (voir _lire_lignes_brutes, décide csv/xlsx par
        extension). Voir §6.4bis : "rien n'est écrit en base tant que
        l'admin n'a pas validé l'écran de relecture dans son ensemble"."""
        lignes_brutes = _lire_lignes_brutes(nom_fichier, fichier)
        if not lignes_brutes:
            raise ValueError("Fichier vide.")
        entetes = [str(c).strip() if c is not None else "" for c in lignes_brutes[0]]
        if len(entetes) < 2:
            raise ValueError(
                'Le fichier doit avoir au moins 2 colonnes : "Nom adhérent" et "Prénom '
                'adhérent" (ou équivalent), dans cet ordre.'
            )

        # Contrainte annoncée à l'utilisateur : les 2 PREMIÈRES colonnes
        # doivent ressembler à Nom/Prénom (voir _ressemble ci-dessus) —
        # jamais de recherche ailleurs dans le fichier pour ces 2-là,
        # contrairement aux autres champs fixes plus bas (l'ordre des 2
        # premières colonnes, lui, est une vraie contrainte du format).
        if not _ressemble(entetes[0], "nom") or _ressemble(entetes[0], "prenom"):
            raise ValueError(
                f'La 1re colonne ("{entetes[0]}") doit ressembler à "Nom" '
                '(ex. "Nom adhérent").'
            )
        if not _ressemble(entetes[1], "prenom"):
            raise ValueError(
                f'La 2e colonne ("{entetes[1]}") doit ressembler à "Prénom" '
                '(ex. "Prénom adhérent").'
            )

        deja_pris = {0, 1}
        idx_email = _trouver_colonne(entetes, deja_pris, "email", "mail")
        if idx_email is not None:
            deja_pris.add(idx_email)
        idx_telephone = _trouver_colonne(entetes, deja_pris, "telephone", "tel")
        if idx_telephone is not None:
            deja_pris.add(idx_telephone)
        idx_adresse = _trouver_colonne(entetes, deja_pris, "adresse")
        if idx_adresse is not None:
            deja_pris.add(idx_adresse)
        idx_naissance = _trouver_colonne(entetes, deja_pris, "naissance", "age", "date")
        if idx_naissance is not None:
            deja_pris.add(idx_naissance)
        idx_contact = _trouver_colonne(entetes, deja_pris, "parent")
        if idx_contact is not None:
            deja_pris.add(idx_contact)

        # (index, en_tete) plutôt que juste l'en_tete : évite une relecture
        # fragile par `.index()` plus bas (2 colonnes pourraient, en
        # théorie, partager le même libellé).
        colonnes_cours = [
            (i, e) for i, e in enumerate(entetes) if e and i not in deja_pris
        ]
        resolues, non_reconnues = self.resoudre_colonnes_cours(
            db, ecole_id, [e for _, e in colonnes_cours]
        )

        def valeur(ligne, index):
            return ligne[index] if index is not None and index < len(ligne) else None

        lignes: list[LigneApercu] = []
        # Détecte les lignes en double DANS LE MÊME FICHIER (vécu : un
        # fichier réel avec 2 lignes identiques pour la même personne) —
        # sans ça, chaque ligne est comparée uniquement à l'état de la
        # base AVANT cet import, donc les 2 lignes se voient chacune comme
        # "nouvel élève" et sont toutes les 2 créées (bug signalé). Jamais
        # fusionnées automatiquement (demande utilisateur explicite : "il
        # faut le signaler ... et permettre à l'utilisateur de choisir
        # entre les 2") — juste signalées, décochées par défaut, à l'admin
        # de choisir laquelle garder (voir `doublon_fichier`).
        index_nouveaux: dict[tuple[str, str], list[int]] = {}  # (nom, prénom normalisés) -> index dans `lignes`
        # Idem pour 2 lignes du fichier visant le MÊME élève déjà en base
        # (même bug, variante moins grave : le doublon s'affiche 2 fois à
        # la relecture au lieu d'être créé 2 fois).
        index_existants: dict[int, int] = {}

        for numero, ligne in enumerate(lignes_brutes[1:], start=2):
            nom = str(valeur(ligne, 0) or "").strip()
            prenom = str(valeur(ligne, 1) or "").strip()
            if not nom and not prenom:
                continue  # ligne vide (ex. fin de fichier)

            brut_email = valeur(ligne, idx_email)
            email = str(brut_email).strip() or None if brut_email else None
            telephone, telephone_suspect = _telephone_texte(valeur(ligne, idx_telephone))
            brut_adresse = valeur(ligne, idx_adresse)
            adresse = str(brut_adresse).strip() or None if brut_adresse else None
            date_naissance = _extraire_date_naissance(valeur(ligne, idx_naissance))
            brut_contact = valeur(ligne, idx_contact)
            contact_parent_brut = str(brut_contact).strip() if brut_contact else None

            cours_ids_fichier = [
                resolues[c] for i, c in colonnes_cours if c in resolues and valeur(ligne, i)
            ]
            colonnes_non_reconnues_ligne = [
                c for i, c in colonnes_cours if c in non_reconnues and valeur(ligne, i)
            ]

            eleve_existant_id, ambigu = self._trouver_eleve_existant(db, ecole_id, nom, prenom, date_naissance)

            if eleve_existant_id is not None:
                index_deja = index_existants.get(eleve_existant_id)
                if index_deja is not None:
                    # Même élève déjà rencontré plus haut dans ce fichier —
                    # fusionne les cours au lieu de le lister 2 fois.
                    deja = lignes[index_deja]
                    deja.cours_ids = sorted(set(deja.cours_ids) | set(cours_ids_fichier))
                    continue
                differences = self._differences(
                    db, eleve_existant_id, email, telephone, adresse, date_naissance, cours_ids_fichier
                )
                cours_a_ajouter = next(
                    (d.valeur_fichier for d in differences if d.champ == "cours"), []
                )
                lignes.append(
                    LigneApercu(
                        numero_ligne=numero, nom=nom, prenom=prenom, email=email,
                        telephone=telephone, telephone_suspect=telephone_suspect, adresse=adresse,
                        date_naissance=date_naissance, contact_parent_brut=contact_parent_brut,
                        cours_ids=cours_a_ajouter, colonnes_non_reconnues=colonnes_non_reconnues_ligne,
                        eleve_existant_id=eleve_existant_id, differences=differences,
                    )
                )
                index_existants[eleve_existant_id] = len(lignes) - 1
                continue

            nouvelle = LigneApercu(
                numero_ligne=numero, nom=nom, prenom=prenom, email=email,
                telephone=telephone, telephone_suspect=telephone_suspect, adresse=adresse,
                date_naissance=date_naissance, contact_parent_brut=contact_parent_brut,
                cours_ids=cours_ids_fichier, colonnes_non_reconnues=colonnes_non_reconnues_ligne,
                # Ambigu (plusieurs homonymes déjà en base, indépartageables)
                # : jamais créé sans décision explicite de l'admin — sinon
                # cette ligne redevient "nouvelle" à CHAQUE réimport, tant
                # qu'elle reste indépartageable, et en recrée une copie à
                # chaque fois (bug signalé : "les rajoute à chaque fois").
                ambigu=ambigu, creer=not ambigu,
            )
            cle = (_normaliser(nom), _normaliser(prenom))
            groupe = index_nouveaux.setdefault(cle, [])
            # Homonyme DANS LE FICHIER : signalé seulement si la date de
            # naissance ne les distingue pas déjà clairement (sinon ce
            # sont 2 personnes différentes qui partagent juste un nom,
            # ex. jumeaux — chacune créée normalement, sans avertissement).
            doublon = any(
                lignes[i].date_naissance is None or date_naissance is None
                or lignes[i].date_naissance == date_naissance
                for i in groupe
            )
            if doublon:
                for i in groupe:
                    lignes[i].doublon_fichier = True
                    lignes[i].creer = False
                nouvelle.doublon_fichier = True
                nouvelle.creer = False
            groupe.append(len(lignes))
            lignes.append(nouvelle)

        return ApercuImport(
            lignes=lignes, colonnes_non_reconnues_globales=sorted(set(non_reconnues))
        )

    def _trouver_eleve_existant(
        self, db: Session, ecole_id: int, nom: str, prenom: str, date_naissance: dt.date | None
    ) -> tuple[int | None, bool]:
        """Correspondance par (nom, prénom) — voir §6.4bis : l'email est
        volontairement exclu (frères/sœurs qui le partagent). La date de
        naissance n'est PLUS une condition stricte (elle peut elle-même
        être une différence à corriger, voir _differences) — elle ne sert
        qu'à départager s'il existe plusieurs homonymes exacts (rare,
        ex. 2 élèves same nom+prénom). Renvoie (id trouvé ou None, ambigu :
        plusieurs homonymes indépartageables — voir appelant, jamais créé
        automatiquement dans ce cas, contrairement à "aucun homonyme" qui,
        lui, veut clairement dire nouvel élève)."""
        candidats = self.eleves.comptes.trouver_par_nom_prenom(db, ecole_id, nom, prenom, role="eleve")
        if not candidats:
            return None, False
        if len(candidats) == 1:
            return candidats[0].id, False
        correspondance_date = [
            c for c in candidats
            if (profil := self.eleves.get_profil(db, c.id)) and profil.date_naissance == date_naissance
        ]
        if len(correspondance_date) == 1:
            return correspondance_date[0].id, False
        return None, True

    def _differences(
        self, db: Session, eleve_id: int, email, telephone, adresse, date_naissance, cours_ids_fichier
    ) -> list[DifferenceChamp]:
        """Une entrée par champ où le fichier apporte une valeur NON VIDE
        différente de la fiche actuelle — jamais l'inverse (une case vide
        dans le fichier n'efface jamais une donnée existante, voir
        `_ajouter` ci-dessous). "cours" : seulement les cours du fichier
        que l'élève n'a PAS déjà (jamais de désinscription automatique —
        un fichier "officiel" peut légitimement ne pas lister tous les
        cours suivis)."""
        compte = self.eleves.get_compte(db, eleve_id)
        profil = self.eleves.get_profil(db, eleve_id)
        differences: list[DifferenceChamp] = []

        def _ajouter(champ: str, actuelle, fichier):
            if fichier is None or fichier == "":
                return
            if fichier != actuelle:
                differences.append(DifferenceChamp(champ=champ, valeur_actuelle=actuelle, valeur_fichier=fichier))

        _ajouter("email", compte.email if compte else None, email)
        _ajouter("telephone", compte.telephone if compte else None, telephone)
        _ajouter("adresse", profil.adresse if profil else None, adresse)
        _ajouter("date_naissance", profil.date_naissance if profil else None, date_naissance)

        cours_actuels_ids = {c.id for c in self.cours.cours_de_leleve(db, eleve_id)}
        cours_a_ajouter = [cid for cid in cours_ids_fichier if cid not in cours_actuels_ids]
        if cours_a_ajouter:
            differences.append(
                DifferenceChamp(champ="cours", valeur_actuelle=None, valeur_fichier=cours_a_ajouter)
            )

        return differences

    # --- Écriture en base (phase 2 : après validation admin) ---

    def valider(self, db: Session, ecole_id: int, lignes: list[LigneApercu]) -> dict:
        """`lignes` : celles renvoyées par `previsualiser`, avec `creer`
        (nouvel élève) ou `champs_a_appliquer` (élève existant, voir
        LigneApercu) éventuellement corrigés par l'admin à la relecture —
        cet ajustement est fait par l'appelant/le frontend avant d'appeler
        `valider`, pas ici."""
        crees = mis_a_jour = inchanges = 0
        for ligne in lignes:
            if ligne.eleve_existant_id is None:
                if not ligne.creer:
                    continue
                compte, _profil = self.eleves.create(
                    db, ecole_id, nom=ligne.nom, prenom=ligne.prenom, email=ligne.email,
                    telephone=ligne.telephone, date_naissance=ligne.date_naissance, adresse=ligne.adresse,
                )
                eleve_id = compte.id
                crees += 1
                if ligne.contact_parent_brut:
                    # "Nom-Prénom parent" (voir §6.4bis) — pas de lien
                    # (père/mère) dans le fichier, laissé vide.
                    contact_nom, contact_prenom = _decouper_nom_prenom_contact(ligne.contact_parent_brut)
                    self.eleves.ajouter_contact(
                        db, eleve_id, nom=contact_nom, prenom=contact_prenom,
                        telephone=ligne.telephone, email=ligne.email,
                    )
                for cours_id in ligne.cours_ids:
                    self.cours.inscrire_eleve(db, cours_id, eleve_id)
                continue

            eleve_id = ligne.eleve_existant_id
            champs_compte: dict = {}
            champs_profil: dict = {}
            if "email" in ligne.champs_a_appliquer:
                champs_compte["email"] = ligne.email
            if "telephone" in ligne.champs_a_appliquer:
                champs_compte["telephone"] = ligne.telephone
            if "adresse" in ligne.champs_a_appliquer:
                champs_profil["adresse"] = ligne.adresse
            if "date_naissance" in ligne.champs_a_appliquer:
                champs_profil["date_naissance"] = ligne.date_naissance
            if champs_compte:
                self.eleves.comptes.update(db, eleve_id, **champs_compte)
            if champs_profil:
                self.eleves.update_profil(db, eleve_id, **champs_profil)
            cours_applique = "cours" in ligne.champs_a_appliquer
            if cours_applique:
                cours_actuels = {c.id for c in self.cours.cours_de_leleve(db, eleve_id)}
                for cours_id in ligne.cours_ids:
                    if cours_id not in cours_actuels:
                        self.cours.inscrire_eleve(db, cours_id, eleve_id)
            if champs_compte or champs_profil or cours_applique:
                mis_a_jour += 1
            else:
                inchanges += 1

        return {"crees": crees, "mis_a_jour": mis_a_jour, "inchanges": inchanges}
