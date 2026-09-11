"""Écrit chaque inscription dans un fichier Excel "nouvelles inscriptions"
SÉPARÉ du fichier maître réel des adhérents (voir spec/SPEC-inscription.md
— décision prise avec l'utilisateur : l'admin fusionne lui-même à la main
quand il veut, jamais d'écriture automatique dans le fichier maître, pour
éviter toute corruption si l'admin l'a ouvert dans Excel en même temps).

En-têtes EXACTS du fichier maître réel (pour faciliter la fusion manuelle) :
Nom adhérent, Prénom adhérent, Nom - Prénom parent, E-Mail, Adresse,
Téléphone, Age, puis une colonne par cours (voir spec/SPEC.md §6.5, "X" si
choisi) — même format "date = age" que l'import (voir
eleves/import_excel.py:_extraire_date_naissance).
"""

from __future__ import annotations

import fcntl
from pathlib import Path

from eleves.eleves import calculer_age
from openpyxl import Workbook, load_workbook

from .models import Inscription

COLONNES_FIXES = [
    "Nom adhérent",
    "Prénom adhérent",
    "Nom - Prénom parent",
    "E-Mail",
    "Adresse",
    "Téléphone",
    "Age",
]

# Les 17 cours officiels (voir spec/SPEC.md §6.5), dans l'ordre exact des
# colonnes du fichier — même liste que tarifs.PALIER_PAR_COURS.
NOMS_COURS = [
    "Éveil",
    "Class Ini",
    "Jazz Ini",
    "Class Moy",
    "Jazz Moy",
    "Street Moyen",
    "Jazz Junior",
    "Street Junior Inter",
    "Class Inter",
    "Jazz Inter",
    "Pointes inter",
    "Pointes AV",
    "Class AV",
    "Jazz AV",
    "Contempo Junior",
    "Contempo Inter avance",
    "Contempo Adulte",
]


def nom_fichier(ecole_id: int, saison: str) -> str:
    return f"nouvelles_inscriptions_{ecole_id}_{saison}.xlsx"


def _en_tetes() -> list[str]:
    return COLONNES_FIXES + NOMS_COURS


def _ligne(inscription: Inscription, noms_cours_choisis: list[str]) -> list:
    age = calculer_age(inscription.eleve_date_naissance)
    date_age = f"{inscription.eleve_date_naissance.strftime('%d/%m/%Y')} = {age} ans"
    contact_parent = " ".join(
        part
        for part in (inscription.contact_urgence_nom, inscription.contact_urgence_prenom)
        if part
    )
    ligne = [
        inscription.eleve_nom,
        inscription.eleve_prenom,
        contact_parent or None,
        inscription.eleve_email,
        inscription.eleve_adresse,
        inscription.eleve_telephone,
        date_age,
    ]
    ligne += ["X" if nom in noms_cours_choisis else None for nom in NOMS_COURS]
    return ligne


def ajouter_ligne(chemin: Path, inscription: Inscription, noms_cours_choisis: list[str]) -> None:
    """Crée le classeur avec les bons en-têtes s'il n'existe pas encore,
    sinon charge et ajoute une ligne. Verrou de fichier (`.lock`
    compagnon) pendant l'écriture — évite une collision entre deux
    soumissions simultanées, raison même de la séparation de ce fichier
    du fichier maître réel."""
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin_verrou = chemin.with_suffix(chemin.suffix + ".lock")

    with open(chemin_verrou, "w") as verrou:
        fcntl.flock(verrou, fcntl.LOCK_EX)
        try:
            if chemin.exists():
                classeur = load_workbook(chemin)
                feuille = classeur.active
            else:
                classeur = Workbook()
                feuille = classeur.active
                feuille.title = "Nouvelles inscriptions"
                feuille.append(_en_tetes())
            feuille.append(_ligne(inscription, noms_cours_choisis))
            classeur.save(chemin)
        finally:
            fcntl.flock(verrou, fcntl.LOCK_UN)
