"""Logique métier des inscriptions (voir spec/SPEC-inscription.md) :
orchestre le calcul du tarif, la détection doublon/famille, la génération
des PDF, l'ajout de la ligne Excel et l'envoi de l'email de confirmation.

Chaque étape APRÈS l'insertion en base est dans son propre try/except,
jamais bloquante (même philosophie que
notifications.py:envoyer_a_compte) : un échec PDF/Excel/email est
journalisé sur la ligne, jamais renvoyé en erreur HTTP à la famille qui
vient de s'inscrire."""

from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path

from cours import CoursService
from ecoles.models import Ecole
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import excel_export
from .email_envoi import EmailEnvoi
from .models import Inscription, inscriptions_cours
from .pdf import generer_dossier_pdf, generer_facture_pdf
from .saison import saison_actuelle
from .schemas import InscriptionCreation
from .stockage import chemin_relatif, dossier_ecole
from .tarifs import calculer_tarif

logger = logging.getLogger(__name__)


class Inscriptions:
    def __init__(self, cours: CoursService) -> None:
        self.cours = cours
        self.email = EmailEnvoi()

    def _resoudre_noms_cours(self, db: Session, ecole_id: int, cours_ids: list[int]) -> list[str]:
        cours_ecole = {c.id: c.nom for c in self.cours.list(db, ecole_id)}
        return [cours_ecole[cid] for cid in cours_ids if cid in cours_ecole]

    def _detecter_doublon_et_famille(
        self, db: Session, ecole_id: int, saison: str, nom: str, prenom: str, email: str | None
    ) -> tuple[bool, bool]:
        """(doublon_possible, reduction_famille) — cherche parmi les
        `Inscription` existantes de la MÊME école + saison uniquement
        (jamais le fichier maître réel, pas nécessaire puisque le tarif
        reste informatif en phase 1). Doublon : même nom+prénom. Famille
        (réduction) : même email, élève différent (voir spec/SPEC.md, PDF
        page tarifs : "-5€/élève dès 2 membres")."""
        existantes = list(
            db.scalars(
                select(Inscription).where(
                    Inscription.ecole_id == ecole_id, Inscription.saison == saison
                )
            )
        )
        doublon = any(
            i.eleve_nom.strip().lower() == nom.strip().lower()
            and i.eleve_prenom.strip().lower() == prenom.strip().lower()
            for i in existantes
        )
        famille = bool(email) and any(
            i.eleve_email
            and i.eleve_email.strip().lower() == email.strip().lower()
            and not (
                i.eleve_nom.strip().lower() == nom.strip().lower()
                and i.eleve_prenom.strip().lower() == prenom.strip().lower()
            )
            for i in existantes
        )
        return doublon, famille

    def creer(
        self, db: Session, ecole_id: int, donnees: InscriptionCreation, ip: str | None
    ) -> Inscription:
        noms_cours = self._resoudre_noms_cours(db, ecole_id, donnees.cours_ids)
        saison = saison_actuelle()
        doublon, famille_detectee = self._detecter_doublon_et_famille(
            db, ecole_id, saison, donnees.eleve_nom, donnees.eleve_prenom, donnees.eleve_email
        )
        # Détection automatique OU auto-déclaration de la famille (voir
        # schemas.py:reduction_famille_demandee — un frère/sœur déjà
        # inscrit mais pas via ce formulaire en ligne échappe à la
        # détection automatique).
        famille = famille_detectee or donnees.reduction_famille_demandee
        tarif = calculer_tarif(noms_cours, reduction_famille=famille)

        inscription = Inscription(
            ecole_id=ecole_id,
            token_public=str(uuid.uuid4()),
            saison=saison,
            ip_soumission=ip,
            eleve_nom=donnees.eleve_nom,
            eleve_prenom=donnees.eleve_prenom,
            eleve_date_naissance=donnees.eleve_date_naissance,
            eleve_adresse=donnees.eleve_adresse,
            eleve_telephone=donnees.eleve_telephone,
            eleve_email=donnees.eleve_email,
            allergies=donnees.allergies,
            traitement_medical=donnees.traitement_medical,
            informations_importantes=donnees.informations_importantes,
            contact_urgence_nom=donnees.contact_urgence_nom,
            contact_urgence_prenom=donnees.contact_urgence_prenom,
            contact_urgence_lien=donnees.contact_urgence_lien,
            contact_urgence_telephone=donnees.contact_urgence_telephone,
            droit_image_autorise=donnees.droit_image_autorise,
            droit_image_site=donnees.droit_image_site,
            droit_image_reseaux=donnees.droit_image_reseaux,
            droit_image_affiches=donnees.droit_image_affiches,
            reglement_lu_approuve=donnees.reglement_lu_approuve,
            signataire_nom=donnees.signataire_nom,
            moyen_paiement=donnees.moyen_paiement,
            palier_tarifaire=tarif.palier,
            nb_cours_semaine=tarif.nb_cours_semaine,
            montant_adhesion=tarif.montant_adhesion,
            montant_mensuel_septembre=tarif.montant_mensuel_septembre,
            montant_trimestriel=tarif.montant_trimestriel,
            reduction_famille_appliquee=tarif.reduction_famille_appliquee,
            alerte_palier_mixte=tarif.alerte_palier_mixte,
            doublon_possible=doublon,
        )
        db.add(inscription)
        db.commit()
        db.refresh(inscription)

        for cours_id in donnees.cours_ids:
            db.execute(
                inscriptions_cours.insert().values(
                    inscription_id=inscription.id, cours_id=cours_id
                )
            )
        db.commit()

        self._generer_pdf(db, inscription, noms_cours)
        self._exporter_excel(db, inscription, noms_cours)
        self._envoyer_email(db, inscription, noms_cours)

        return inscription

    def _generer_pdf(self, db: Session, inscription: Inscription, noms_cours: list[str]) -> None:
        try:
            dossier = dossier_ecole(inscription.ecole_id)
            nom_dossier = f"{inscription.token_public}-dossier.pdf"
            nom_facture = f"{inscription.token_public}-facture.pdf"
            chemin_photo = (
                dossier_ecole(inscription.ecole_id) / Path(inscription.eleve_photo_chemin).name
                if inscription.eleve_photo_chemin
                else None
            )
            (dossier / nom_dossier).write_bytes(
                generer_dossier_pdf(inscription, noms_cours, chemin_photo)
            )
            (dossier / nom_facture).write_bytes(generer_facture_pdf(inscription))
            inscription.pdf_dossier_chemin = chemin_relatif(inscription.ecole_id, nom_dossier)
            inscription.pdf_facture_chemin = chemin_relatif(inscription.ecole_id, nom_facture)
            db.commit()
        except Exception:
            logger.exception(
                "Génération PDF échouée pour l'inscription %s", inscription.token_public
            )

    def _exporter_excel(
        self, db: Session, inscription: Inscription, noms_cours: list[str]
    ) -> None:
        try:
            chemin = dossier_ecole(inscription.ecole_id) / excel_export.nom_fichier(
                inscription.ecole_id, inscription.saison
            )
            excel_export.ajouter_ligne(chemin, inscription, noms_cours)
        except Exception:
            logger.exception(
                "Ajout Excel échoué pour l'inscription %s", inscription.token_public
            )

    def _envoyer_email(self, db: Session, inscription: Inscription, noms_cours: list[str]) -> None:
        if not inscription.eleve_email:
            return
        try:
            ecole = db.get(Ecole, inscription.ecole_id)
            nom_ecole = ecole.nom if ecole is not None else "Contretemps"
            pieces_jointes = []
            if inscription.pdf_dossier_chemin:
                dossier = dossier_ecole(inscription.ecole_id)
                pieces_jointes.append(
                    (
                        "dossier-inscription.pdf",
                        (dossier / f"{inscription.token_public}-dossier.pdf").read_bytes(),
                    )
                )
                pieces_jointes.append(
                    (
                        "facture.pdf",
                        (dossier / f"{inscription.token_public}-facture.pdf").read_bytes(),
                    )
                )
            self.email.envoyer_confirmation(
                inscription.eleve_email,
                f"Inscription validée à l'école de danse {nom_ecole} pour la saison "
                f"{inscription.saison}",
                (
                    f"Bonjour,\n\nNous confirmons la bonne réception de l'inscription de "
                    f"{inscription.eleve_prenom} {inscription.eleve_nom} pour la saison "
                    f"{inscription.saison}. Vous trouverez ci-joint le dossier rempli et la "
                    f"facture correspondante.\n\nÀ bientôt,\nL'équipe {nom_ecole}"
                ),
                pieces_jointes,
            )
            # `envoyer_confirmation` ne fait rien (mais ne lève rien non
            # plus) si le SMTP n'est pas configuré — voir
            # email_envoi.py:actif. Ne marquer "envoyé" que si un envoi a
            # vraiment eu lieu.
            inscription.email_envoye = self.email.actif
        except Exception as erreur:
            logger.exception(
                "Envoi email échoué pour l'inscription %s", inscription.token_public
            )
            inscription.email_erreur = str(erreur)
        finally:
            db.commit()

    def get_par_token(self, db: Session, token: str) -> Inscription | None:
        return db.scalar(select(Inscription).where(Inscription.token_public == token))

    def enregistrer_photo(
        self, db: Session, token: str, fichier, nom_fichier_original: str
    ) -> Inscription | None:
        """Upload de la photo de l'élève, séparé de `creer()` (voir
        FormulaireInscription.jsx : envoyée juste après la création,
        une fois le token connu) — jamais bloquant pour l'inscription
        elle-même si ça échoue (voir receiver.py, même philosophie que
        PDF/Excel/email). `fichier` : objet fichier ouvert en lecture
        binaire (UploadFile.file côté FastAPI), même convention que
        videos.py:creer_avec_upload."""
        inscription = self.get_par_token(db, token)
        if inscription is None:
            return None

        dossier = dossier_ecole(inscription.ecole_id)
        extension = Path(nom_fichier_original).suffix or ".jpg"
        nom_disque = f"{inscription.token_public}-photo{extension}"
        with open(dossier / nom_disque, "wb") as sortie:
            shutil.copyfileobj(fichier, sortie)

        inscription.eleve_photo_chemin = chemin_relatif(inscription.ecole_id, nom_disque)
        db.commit()
        db.refresh(inscription)

        # Régénère le dossier PDF pour y inclure la photo (voir pdf.py) —
        # généré une 1re fois sans elle dans creer(), avant que la photo
        # (uploadée séparément) ne soit connue.
        self._generer_pdf(db, inscription, self.cours_choisis(db, inscription.id))
        return inscription

    def cours_choisis(self, db: Session, inscription_id: int) -> list[str]:
        lignes = db.execute(
            select(inscriptions_cours.c.cours_id).where(
                inscriptions_cours.c.inscription_id == inscription_id
            )
        ).all()
        cours_ids = [ligne[0] for ligne in lignes]
        return [c.nom for c in [self.cours.get(db, cid) for cid in cours_ids] if c is not None]

    def exporter_nouvelles_inscriptions(self, db: Session, ecole_id: int) -> bytes | None:
        """Le classeur "nouvelles inscriptions" courant, en entier (bouton
        admin, voir receiver.py)."""
        saison = saison_actuelle()
        chemin = dossier_ecole(ecole_id) / excel_export.nom_fichier(ecole_id, saison)
        if not chemin.exists():
            return None
        return chemin.read_bytes()
