"""Fiches d'inscription papier lues automatiquement (« Ajouter élève
(OCR) », voir spec/SPEC-inscription.md). Une fiche lue est un BROUILLON :
les champs proposés et les photos, gardés quelques heures dans le dossier
de l'école, le temps que l'admin les corrige dans le formulaire
d'inscription en ligne. « Enregistrer l'élève » l'ajoute alors
DIRECTEMENT à la liste officielle des élèves (Admin > Élèves), sans passer
par les inscriptions en attente ni par le paiement — décision utilisateur
du 2026-10-02 — et envoie à l'administrateur un mail avec, en pièces jointes, le
dossier d'inscription rempli (le même PDF que pour une inscription en ligne)
et les photos de la fiche. Le brouillon est ensuite effacé.

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

from comptes import Compte
from cours import CoursService
from ecoles.models import Ecole
from eleves import Eleves
from sqlalchemy.orm import Session

from . import stockage
from .dossier_html import generer_dossier_pdf
from .email_envoi import EmailEnvoi
from .models import Inscription
from .pdf import nom_fichier_dossier
from .lecture_fiche import TYPE_PDF, TYPES_IMAGE, LectureFiche, Page
from .saison import saison_des_inscriptions
from .schemas import InscriptionCreation
from .tarifs import NB_TRIMESTRES, calculer_tarif

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


def _commentaire(donnees: InscriptionCreation, famille_membres: int = 1) -> str:
    """Ce que la fiche élève ne sait pas ranger ailleurs : droit à l'image
    et règlement intérieur, dans le commentaire de l'admin."""
    if donnees.droit_image_autorise:
        usages = [
            libelle
            for libelle, accorde in (
                ("site internet", donnees.droit_image_site),
                ("réseaux sociaux", donnees.droit_image_reseaux),
                ("affiches", donnees.droit_image_affiches),
            )
            if accorde
        ]
        image = "Droit à l'image : oui" + (f" ({', '.join(usages)})" if usages else "")
    else:
        image = "Droit à l'image : non"
    reglement = (
        f"Règlement signé par {donnees.signataire_nom.strip()}"
        if donnees.reglement_lu_approuve
        else "Règlement non signé"
    )
    jour = dt.date.today().strftime("%d/%m/%Y")
    famille = f" Famille {famille_membres} membres." if famille_membres >= 2 else ""
    return f"Fiche papier du {jour}. {image}. {reglement}.{famille}"


def _jeton_valide(jeton: str) -> bool:
    # Le jeton entre dans un nom de fichier : rien d'autre qu'un UUID.
    try:
        return str(uuid.UUID(jeton)) == jeton
    except ValueError:
        return False


class EleveDejaInscrit(Exception):
    """Un élève de l'école porte déjà ce nom et ce prénom."""


class FichesPapier:
    def __init__(
        self, cours: CoursService, eleves: Eleves, lecture: LectureFiche | None = None
    ) -> None:
        self.cours = cours
        self.eleves = eleves
        self.lecture = lecture or LectureFiche()
        self.email = EmailEnvoi()

    def lire(
        self, db: Session, ecole_id: int, pages: list[Page], famille_membres: int | None = None
    ) -> dict:
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
        # Fiches d'une même famille lues d'un coup (« Galerie multi-membres ») :
        # le nombre de membres est connu, quoi que dise la fiche.
        if famille_membres in (2, 3):
            donnees["famille_membres"] = famille_membres
            douteux.discard("famille_membres")
        if donnees["famille_membres"] not in (1, 2, 3):
            donnees["famille_membres"] = 1
            douteux.add("famille_membres")
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

    def enregistrer_eleve(
        self, db: Session, jeton: str, donnees: InscriptionCreation, malgre_homonyme: bool = False
    ) -> dict | None:
        """Ajoute l'élève à la liste officielle de l'école, avec ses cours
        et son contact d'urgence, prévient l'administrateur par mail (photos
        de la fiche jointes), puis efface le brouillon. `None` si le
        brouillon n'existe plus."""
        brouillon = self.obtenir(jeton)
        if brouillon is None:
            return None
        ecole_id = brouillon["ecole_id"]
        nom, prenom = donnees.eleve_nom.strip(), donnees.eleve_prenom.strip()
        if not malgre_homonyme and self.eleves.comptes.trouver_par_nom_prenom(
            db, ecole_id, nom, prenom, role="eleve"
        ):
            raise EleveDejaInscrit()

        cours_ecole = {c.id: c.nom for c in self.cours.list(db, ecole_id)}
        cours_ids = [cid for cid in dict.fromkeys(donnees.cours_ids) if cid in cours_ecole]
        tarif = calculer_tarif(
            [cours_ecole[cid] for cid in cours_ids],
            reduction_famille=donnees.reduction_famille_demandee,
            famille_membres=donnees.famille_membres,
        )
        compte, _ = self.eleves.create(
            db,
            ecole_id=ecole_id,
            nom=nom,
            prenom=prenom,
            email=(donnees.eleve_email or "").strip() or None,
            telephone=donnees.eleve_telephone,
            date_naissance=donnees.eleve_date_naissance,
            adresse=donnees.eleve_adresse,
            allergies=donnees.allergies,
            traitement_medical=donnees.traitement_medical,
            informations_importantes=donnees.informations_importantes,
            montant_total_annee=tarif.montant_adhesion + tarif.montant_trimestriel * NB_TRIMESTRES,
            commentaire_admin=_commentaire(donnees, tarif.famille_membres),
        )
        for cours_id in cours_ids:
            self.cours.inscrire_eleve(db, cours_id, compte.id)
        if donnees.contact_urgence_nom or donnees.contact_urgence_prenom or donnees.contact_urgence_telephone:
            self.eleves.ajouter_contact(
                db,
                compte.id,
                nom=donnees.contact_urgence_nom,
                prenom=donnees.contact_urgence_prenom,
                lien=donnees.contact_urgence_lien,
                telephone=donnees.contact_urgence_telephone,
            )

        saison = saison_des_inscriptions(db, ecole_id)
        ecole = db.get(Ecole, ecole_id)
        nom_ecole = ecole.nom if ecole is not None else "Contretemps"
        dossier_pdf = self._dossier_pdf(compte, donnees, saison, [cours_ecole[cid] for cid in cours_ids])
        mail_envoye = self._prevenir_admin(compte, saison, nom_ecole, brouillon, dossier_pdf)
        self.supprimer(jeton)
        return {
            "eleve_id": compte.id,
            "eleve_nom": compte.nom,
            "eleve_prenom": compte.prenom,
            "saison": saison,
            "mail_envoye": mail_envoye,
            "mail_adresse": self.email.adresse_admin if mail_envoye else None,
            "cout_usd": brouillon["cout_usd"],
        }

    def _dossier_pdf(
        self, compte: Compte, donnees: InscriptionCreation, saison: str, noms_cours: list[str]
    ) -> tuple[str, bytes] | None:
        """Le même dossier PDF que celui d'une inscription en ligne (voir
        dossier_html.py), avec les champs validés par l'admin. Il se
        fabrique à partir d'une inscription : on lui en présente une,
        jamais enregistrée. Jamais bloquant."""
        try:
            fictive = Inscription(
                **donnees.model_dump(exclude={"cours_ids", "reduction_famille_demandee", "famille_membres"}),
                id=compte.id,
                saison=saison,
                created_at=dt.datetime.now(dt.UTC),
                ip_soumission=None,
                alerte_palier_mixte=False,
            )
            return nom_fichier_dossier(fictive), generer_dossier_pdf(fictive, noms_cours, None)
        except Exception:
            logger.exception("Dossier PDF non généré pour la fiche papier (élève %s)", compte.id)
            return None

    def _prevenir_admin(
        self,
        compte: Compte,
        saison: str,
        nom_ecole: str,
        brouillon: dict,
        dossier_pdf: tuple[str, bytes] | None,
    ) -> bool:
        """Jamais bloquant : l'élève est déjà enregistré."""
        if not self.email.actif:
            return False
        try:
            dossier = stockage.dossier_ecole(brouillon["ecole_id"])
            pieces = [dossier_pdf] if dossier_pdf else []
            for numero, page in enumerate(brouillon["pages"], start=1):
                chemin = dossier / page["nom"]
                if chemin.exists():
                    pieces.append((f"fiche-{numero}{chemin.suffix}", chemin.read_bytes()))
            nom_complet = f"{compte.prenom} {compte.nom}"
            self.email.envoyer_confirmation(
                self.email.adresse_admin,
                # Titre demandé par l'utilisateur (2026-10-02).
                f"Inscription papier validée de {nom_complet} à l'école {nom_ecole} pour la saison {saison}",
                (
                    f"Bonjour,\n\nL'élève {nom_complet} est désormais inscrit(e) pour la saison "
                    f"{saison} de {nom_ecole}, à partir de sa fiche d'inscription papier. Il ou elle figure "
                    "dans la liste des élèves de l'application.\n\nEn pièces jointes : "
                    "le dossier d'inscription rempli, et les photos de la fiche papier."
                ),
                pieces,
            )
            return True
        except Exception:
            logger.exception("Mail d'inscription par fiche papier non envoyé (élève %s)", compte.id)
            return False

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
