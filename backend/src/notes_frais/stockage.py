"""Rangement des justificatifs sur le disque, en enveloppes (décision de
Seb, 16 octobre) :

    <racine>/<org_id>/<person_id> <Nom>/
        depenses/                              tickets pas encore envoyés
        notes/<AAAA-MM-JJ> <titre> (<id>)/     une enveloppe par note envoyée

À l'envoi, les fichiers passent de `depenses/` à l'enveloppe de la note ;
une note reprise les y renvoie. Chaque enveloppe contient aussi
« Note de frais.pdf » (récapitulatif et photos, voir recapitulatif.py),
refait à chaque étape. Le dossier d'une personne commence par son
numéro (stable d'une saison à l'autre) : il est retrouvé même si son nom
change. Jamais servis en accès direct : seulement par les routes du module.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import BinaryIO

BLOC = 1024 * 1024
_INTERDITS = re.compile(r'[\x00-\x1f/\\:*?"<>|]+')


class FichierTropLourd(ValueError):
    pass


def nom_propre(texte: str, longueur: int = 60) -> str:
    """Utilisable comme nom de fichier ou de dossier sur tous les systèmes."""
    propre = " ".join(_INTERDITS.sub(" ", texte or "").split()).strip(" .")
    return propre[:longueur].strip(" .") or "sans nom"


def nom_dossier(texte: str, longueur: int = 60) -> str:
    """Nom de dossier de Docs en majuscules sans accent (« Agnès Pesenti »
    → « AGNES PESENTI », règle de Seb du 30 octobre 2026)."""
    import unicodedata

    sans_accent = "".join(c for c in unicodedata.normalize("NFD", texte or "") if unicodedata.category(c) != "Mn")
    return nom_propre(sans_accent.upper(), longueur)


class StockageEnveloppes:
    def __init__(self, root: Path, max_bytes: int) -> None:
        self.root = Path(root)
        self.max_bytes = max_bytes

    def _org(self, org_id: int) -> Path:
        return self.root / str(org_id)

    def chemin(self, org_id: int, relatif: str) -> Path:
        cible = (self._org(org_id) / relatif).resolve()
        if not cible.is_relative_to(self._org(org_id).resolve()):
            raise LookupError("Chemin de justificatif invalide.")
        return cible

    def dossier_personne(self, org_id: int, person_id: int, nom: str) -> str:
        """`<person_id> <Nom>`, ou le dossier déjà créé pour ce numéro."""
        org = self._org(org_id)
        if org.exists():
            for dossier in org.iterdir():
                if dossier.is_dir() and dossier.name.split(" ", 1)[0] == str(person_id):
                    return dossier.name
        return f"{person_id} {nom_propre(nom)}"

    def dossier_depenses(self, org_id: int, person_id: int, nom: str) -> str:
        return f"{self.dossier_personne(org_id, person_id, nom)}/depenses"

    def dossier_note(self, org_id: int, person_id: int, nom: str, jour: str, titre: str, note_id: int) -> str:
        return f"{self.dossier_personne(org_id, person_id, nom)}/notes/{jour} {nom_propre(titre)} ({note_id})"

    def _libre(self, dossier: Path, nom_fichier: str) -> Path:
        cible = dossier / nom_fichier
        base, extension = os.path.splitext(nom_fichier)
        n = 2
        while cible.exists():
            cible = dossier / f"{base} ({n}){extension}"
            n += 1
        return cible

    def put(self, org_id: int, dossier: str, nom_fichier: str, source: BinaryIO) -> tuple[str, int]:
        """Écrit `source` dans `dossier` ; renvoie (chemin relatif, taille).
        Écrit d'abord un fichier temporaire, déplacé une fois complet."""
        cible_dossier = self.chemin(org_id, dossier)
        cible_dossier.mkdir(parents=True, exist_ok=True)
        descripteur, temporaire = tempfile.mkstemp(dir=cible_dossier, prefix=".envoi-")
        taille = 0
        try:
            with os.fdopen(descripteur, "wb") as sortie:
                while bloc := source.read(BLOC):
                    taille += len(bloc)
                    if taille > self.max_bytes:
                        raise FichierTropLourd(f"Fichier trop lourd (plus de {self.max_bytes // (1024 * 1024)} Mo).")
                    sortie.write(bloc)
            cible = self._libre(cible_dossier, nom_propre(nom_fichier, 100))
            shutil.move(temporaire, cible)
            return cible.relative_to(self._org(org_id).resolve()).as_posix(), taille
        except BaseException:
            if os.path.exists(temporaire):
                os.unlink(temporaire)
            raise

    def ecrire(self, org_id: int, dossier: str, nom_fichier: str, contenu: bytes) -> str:
        """Écrit (ou remplace) `nom_fichier` dans `dossier` ; renvoie son
        chemin relatif. Fichier temporaire d'abord : jamais à moitié écrit."""
        cible_dossier = self.chemin(org_id, dossier)
        cible_dossier.mkdir(parents=True, exist_ok=True)
        descripteur, temporaire = tempfile.mkstemp(dir=cible_dossier, prefix=".envoi-")
        with os.fdopen(descripteur, "wb") as sortie:
            sortie.write(contenu)
        cible = cible_dossier / nom_fichier
        os.replace(temporaire, cible)
        return cible.relative_to(self._org(org_id).resolve()).as_posix()

    def deplacer(self, org_id: int, relatif: str, dossier: str) -> str:
        """Déplace un fichier dans `dossier` ; renvoie son nouveau chemin."""
        source = self.chemin(org_id, relatif)
        cible_dossier = self.chemin(org_id, dossier)
        cible_dossier.mkdir(parents=True, exist_ok=True)
        if not source.exists():
            return relatif
        cible = self._libre(cible_dossier, source.name)
        shutil.move(source, cible)
        self._ranger(source.parent, org_id)
        return cible.relative_to(self._org(org_id).resolve()).as_posix()

    def delete(self, org_id: int, relatif: str) -> None:
        cible = self.chemin(org_id, relatif)
        try:
            cible.unlink()
        except FileNotFoundError:
            return
        self._ranger(cible.parent, org_id)

    def _ranger(self, dossier: Path, org_id: int) -> None:
        """Retire une enveloppe de note restée vide (pas `depenses/`)."""
        if dossier.parent.name == "notes" and dossier.is_dir() and not any(dossier.iterdir()):
            dossier.rmdir()
