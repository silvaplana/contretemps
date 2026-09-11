"""Routes REST des inscriptions — publiques (aucune notion
d'authentification dans ce backend, voir §1 : cohérent avec le reste du
projet), reçoit les requêtes HTTP, délègue tout à Inscriptions (voir
inscriptions.py), ne fait aucun calcul métier ici.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from sqlalchemy.orm import Session

from db import get_db

from .inscriptions import Inscriptions
from .schemas import InscriptionCreation, InscriptionSortie


class InscriptionsReceiver:
    def __init__(self, client: Inscriptions, app: FastAPI) -> None:
        self.client = client
        self.app = app
        self._register_routes()

    def _register_routes(self) -> None:
        self.app.post("/inscriptions", response_model=InscriptionSortie, status_code=201)(
            self.creer
        )
        self.app.post("/inscriptions/{token}/photo", status_code=204)(self.photo)
        self.app.get("/inscriptions/{token}/dossier.pdf")(self.dossier_pdf)
        self.app.get("/inscriptions/{token}/facture.pdf")(self.facture_pdf)
        self.app.get("/inscriptions/export")(self.export)

    def _vers_sortie(self, db: Session, inscription) -> InscriptionSortie:
        return InscriptionSortie(
            token_public=inscription.token_public,
            saison=inscription.saison,
            eleve_nom=inscription.eleve_nom,
            eleve_prenom=inscription.eleve_prenom,
            cours_choisis=self.client.cours_choisis(db, inscription.id),
            palier_tarifaire=inscription.palier_tarifaire,
            nb_cours_semaine=inscription.nb_cours_semaine,
            montant_adhesion=inscription.montant_adhesion,
            montant_mensuel_septembre=inscription.montant_mensuel_septembre,
            montant_trimestriel=inscription.montant_trimestriel,
            reduction_famille_appliquee=inscription.reduction_famille_appliquee,
            alerte_palier_mixte=inscription.alerte_palier_mixte,
            doublon_possible=inscription.doublon_possible,
            moyen_paiement=inscription.moyen_paiement,
            email_envoye=inscription.email_envoye,
        )

    def creer(
        self,
        ecole_id: int,
        donnees: InscriptionCreation,
        request: Request,
        db: Session = Depends(get_db),
    ):
        ip = request.client.host if request.client else None
        inscription = self.client.creer(db, ecole_id, donnees, ip)
        return self._vers_sortie(db, inscription)

    def photo(self, token: str, fichier: UploadFile = File(...), db: Session = Depends(get_db)):
        """Upload de la photo de l'élève, appelé juste après la création
        (voir FormulaireInscription.jsx) — jamais bloquant pour
        l'inscription : un 404 ici (token inconnu) est la seule erreur
        renvoyée, tout le reste (photo illisible...) est absorbé côté
        service (voir inscriptions.py:enregistrer_photo)."""
        inscription = self.client.enregistrer_photo(
            db, token, fichier.file, fichier.filename or "photo.jpg"
        )
        if inscription is None:
            raise HTTPException(status_code=404, detail="Inscription introuvable")

    def dossier_pdf(self, token: str, db: Session = Depends(get_db)):
        inscription = self.client.get_par_token(db, token)
        if inscription is None or not inscription.pdf_dossier_chemin:
            raise HTTPException(status_code=404, detail="Dossier introuvable")
        from .stockage import DOSSIER_INSCRIPTIONS

        chemin = DOSSIER_INSCRIPTIONS / inscription.pdf_dossier_chemin
        if not chemin.exists():
            raise HTTPException(status_code=404, detail="Dossier introuvable")
        return Response(content=chemin.read_bytes(), media_type="application/pdf")

    def facture_pdf(self, token: str, db: Session = Depends(get_db)):
        inscription = self.client.get_par_token(db, token)
        if inscription is None or not inscription.pdf_facture_chemin:
            raise HTTPException(status_code=404, detail="Facture introuvable")
        from .stockage import DOSSIER_INSCRIPTIONS

        chemin = DOSSIER_INSCRIPTIONS / inscription.pdf_facture_chemin
        if not chemin.exists():
            raise HTTPException(status_code=404, detail="Facture introuvable")
        return Response(content=chemin.read_bytes(), media_type="application/pdf")

    def export(self, ecole_id: int, db: Session = Depends(get_db)):
        contenu = self.client.exporter_nouvelles_inscriptions(db, ecole_id)
        if contenu is None:
            raise HTTPException(status_code=404, detail="Aucune nouvelle inscription")
        return Response(
            content=contenu,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=nouvelles_inscriptions.xlsx"},
        )
