"""Fiches d'inscription papier lues automatiquement (« Ajouter élève
(OCR) », voir spec/SPEC-inscription.md). Une fiche lue est un BROUILLON :
les champs proposés et les photos, gardés quelques heures dans le dossier
de l'école, le temps que l'admin les corrige dans le formulaire
d'inscription en ligne. À la validation, l'inscription suit le chemin
habituel (voir inscriptions.py:creer) et les photos de la fiche lui sont
rattachées, comme preuve.

Pas de table : un fichier `fiche-<jeton>.json` et ses pages
`fiche-<jeton>-<n>.<ext>`. Le jeton, tiré au hasard, sert de clé d'accès
au brouillon depuis le formulaire (qui n'a pas de session).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import uuid
from pathlib import Path

from cours import CoursService
from sqlalchemy.orm import Session

from . import stockage
from .lecture_fiche import TYPE_PDF, TYPES_IMAGE, LectureFiche, Page
from .models import Inscription

logger = logging.getLogger(__name__)

DUREE_BROUILLON = dt.timedelta(hours=24)
PAGES_MAX = 4
# L'API refuse une image de plus de 5 Mo une fois encodée ; l'appli réduit
# les photos avant l'envoi (voir frontend, utils/reduirePhoto.js).
TAILLE_MAX_IMAGE = 3_700_000
TAILLE_MAX_PDF = 15_000_000

_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    TYPE_PDF: ".pdf",
}


class FicheInvalide(ValueError):
    """Fichiers refusés ; le message est montrable à l'admin."""


def _jeton_valide(jeton: str) -> bool:
    # Le jeton entre dans un nom de fichier : rien d'autre qu'un UUID.
    try:
        return str(uuid.UUID(jeton)) == jeton
    except ValueError:
        return False


class FichesPapier:
    def __init__(self, cours: CoursService, lecture: LectureFiche | None = None) -> None:
        self.cours = cours
        self.lecture = lecture or LectureFiche()

    def lire(self, db: Session, ecole_id: int, pages: list[Page]) -> dict:
        """Fait lire la fiche et enregistre le brouillon. Lève FicheInvalide
        (fichiers refusés) ou LectureIndisponible (voir lecture_fiche.py)."""
        if not pages:
            raise FicheInvalide("Ajoutez au moins une photo de la fiche.")
        if len(pages) > PAGES_MAX:
            raise FicheInvalide(f"Pas plus de {PAGES_MAX} pages par fiche.")
        for page in pages:
            if page.type_mime not in TYPES_IMAGE and page.type_mime != TYPE_PDF:
                raise FicheInvalide("Seules les photos (JPEG, PNG, WebP) et les PDF sont acceptés.")
            limite = TAILLE_MAX_PDF if page.type_mime == TYPE_PDF else TAILLE_MAX_IMAGE
            if len(page.contenu) > limite:
                raise FicheInvalide("Fichier trop lourd : reprenez la photo ou réduisez-la.")

        cours_ecole = [(c.id, c.nom) for c in self.cours.list(db, ecole_id)]
        resultat = self.lecture.lire(pages, cours_ecole)

        donnees = resultat.fiche.model_dump()
        douteux = set(donnees.pop("champs_douteux"))
        remarques = donnees.pop("remarques")
        ids_connus = {cours_id for cours_id, _ in cours_ecole}
        cours_lus = list(dict.fromkeys(donnees["cours_ids"]))
        donnees["cours_ids"] = [cours_id for cours_id in cours_lus if cours_id in ids_connus]
        if len(donnees["cours_ids"]) != len(cours_lus) or not donnees["cours_ids"]:
            douteux.add("cours_ids")
        # Une case cochée vaut autorisation (décision utilisateur du
        # 2026-10-02), quoi qu'ait conclu la lecture de la mention à rayer.
        cases = ("droit_image_site", "droit_image_reseaux", "droit_image_affiches")
        if any(donnees[case] for case in cases) and "droit_image_autorise" not in douteux:
            donnees["droit_image_autorise"] = True
        if donnees["eleve_date_naissance"]:
            try:
                dt.date.fromisoformat(donnees["eleve_date_naissance"])
            except ValueError:
                donnees["eleve_date_naissance"] = None
                douteux.add("eleve_date_naissance")

        self._purger(ecole_id)
        jeton = str(uuid.uuid4())
        dossier = stockage.dossier_ecole(ecole_id)
        noms_pages = []
        for numero, page in enumerate(pages, start=1):
            nom = f"fiche-{jeton}-{numero}{_EXTENSIONS[page.type_mime]}"
            (dossier / nom).write_bytes(page.contenu)
            noms_pages.append({"nom": nom, "type_mime": page.type_mime})
        brouillon = {
            "jeton": jeton,
            "ecole_id": ecole_id,
            "cree_le": dt.datetime.now(dt.UTC).isoformat(),
            "donnees": donnees,
            "champs_douteux": sorted(douteux & set(donnees)),
            "remarques": remarques,
            "pages": noms_pages,
            "modele": resultat.modele,
            "jetons_entree": resultat.jetons_entree,
            "jetons_sortie": resultat.jetons_sortie,
            "cout_usd": resultat.cout_usd,
        }
        (dossier / f"fiche-{jeton}.json").write_text(json.dumps(brouillon), encoding="utf-8")
        logger.info(
            "Fiche papier lue (école %s) : %s jetons en entrée, %s en sortie, %.4f $",
            ecole_id, resultat.jetons_entree, resultat.jetons_sortie, resultat.cout_usd,
        )
        return brouillon

    def _chemin(self, jeton: str) -> Path | None:
        if not _jeton_valide(jeton):
            return None
        return next(stockage.DOSSIER_INSCRIPTIONS.glob(f"*/fiche-{jeton}.json"), None)

    def obtenir(self, jeton: str) -> dict | None:
        chemin = self._chemin(jeton)
        if chemin is None:
            return None
        brouillon = json.loads(chemin.read_text(encoding="utf-8"))
        if dt.datetime.now(dt.UTC) - dt.datetime.fromisoformat(brouillon["cree_le"]) > DUREE_BROUILLON:
            self.supprimer(jeton)
            return None
        return brouillon

    def page(self, jeton: str, numero: int) -> tuple[bytes, str] | None:
        brouillon = self.obtenir(jeton)
        if brouillon is None or not 1 <= numero <= len(brouillon["pages"]):
            return None
        page = brouillon["pages"][numero - 1]
        chemin = stockage.dossier_ecole(brouillon["ecole_id"]) / page["nom"]
        if not chemin.exists():
            return None
        return chemin.read_bytes(), page["type_mime"]

    def supprimer(self, jeton: str) -> None:
        """Annulation : le brouillon et ses photos disparaissent."""
        chemin = self._chemin(jeton)
        if chemin is None:
            return
        for fichier in chemin.parent.glob(f"fiche-{jeton}*"):
            fichier.unlink(missing_ok=True)

    def rattacher(self, jeton: str, inscription: Inscription) -> None:
        """Inscription validée : les photos de la fiche portent désormais
        son nom (`<token>-fiche-<n>.<ext>`), le brouillon est effacé."""
        chemin = self._chemin(jeton)
        if chemin is None:
            return
        brouillon = json.loads(chemin.read_text(encoding="utf-8"))
        for numero, page in enumerate(brouillon["pages"], start=1):
            source = chemin.parent / page["nom"]
            if source.exists():
                source.rename(
                    chemin.parent / f"{inscription.token_public}-fiche-{numero}{source.suffix}"
                )
        chemin.unlink(missing_ok=True)

    def _purger(self, ecole_id: int) -> None:
        """Brouillons abandonnés depuis plus de 24 heures."""
        limite = dt.datetime.now(dt.UTC) - DUREE_BROUILLON
        for chemin in stockage.dossier_ecole(ecole_id).glob("fiche-*.json"):
            try:
                cree_le = dt.datetime.fromisoformat(json.loads(chemin.read_text(encoding="utf-8"))["cree_le"])
            except (ValueError, KeyError):
                continue
            if cree_le < limite:
                for fichier in chemin.parent.glob(f"{chemin.stem}*"):
                    fichier.unlink(missing_ok=True)
