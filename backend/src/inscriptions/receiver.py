"""Routes REST des inscriptions — publiques (aucune notion
d'authentification dans ce backend, voir §1 : cohérent avec le reste du
projet), reçoit les requêtes HTTP, délègue tout à Inscriptions (voir
inscriptions.py), ne fait aucun calcul métier ici.
"""

from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from sqlalchemy.orm import Session

from db import get_db

from .helloasso import HelloAssoError
from .inscriptions import Inscriptions
from .schemas import (
    InscriptionCreation,
    InscriptionSortie,
    PaiementHelloAssoEntree,
    PaiementHelloAssoSortie,
)

logger = logging.getLogger(__name__)


class InscriptionsReceiver:
    def __init__(self, client: Inscriptions, app: FastAPI) -> None:
        self.client = client
        self.app = app
        self._register_routes()

    def _register_routes(self) -> None:
        self.app.post("/inscriptions", response_model=InscriptionSortie, status_code=201)(
            self.creer
        )
        # "/inscriptions/export" AVANT "/inscriptions/{token}" : sinon
        # FastAPI (routes évaluées dans l'ordre d'enregistrement) fait
        # matcher "export" comme si c'était un token (piège trouvé par
        # un test qui échouait en 404 sur /inscriptions/export).
        self.app.get("/inscriptions/export")(self.export)
        self.app.post("/inscriptions/{token}/photo", status_code=204)(self.photo)
        self.app.get("/inscriptions/{token}", response_model=InscriptionSortie)(self.obtenir)
        self.app.get("/inscriptions/{token}/dossier.pdf")(self.dossier_pdf)
        self.app.get("/inscriptions/{token}/facture.pdf")(self.facture_pdf)
        self.app.post(
            "/inscriptions/{token}/paiement/helloasso", response_model=PaiementHelloAssoSortie
        )(self.initier_paiement_helloasso)
        self.app.post(
            "/inscriptions/{token}/paiement/helloasso/verifier", response_model=InscriptionSortie
        )(self.verifier_paiement_helloasso)
        self.app.post("/inscriptions/paiement/helloasso/notification", status_code=204)(
            self.notification_helloasso
        )

    def _vers_sortie(self, db: Session, inscription) -> InscriptionSortie:
        return InscriptionSortie(
            token_public=inscription.token_public,
            saison=inscription.saison,
            eleve_nom=inscription.eleve_nom,
            eleve_prenom=inscription.eleve_prenom,
            eleve_email=inscription.eleve_email,
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
            paiement_nb_echeances=inscription.paiement_nb_echeances,
            statut_paiement=inscription.statut_paiement,
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

    def obtenir(self, token: str, db: Session = Depends(get_db)):
        """Recharge une inscription par son token — utilisé au retour de
        paiement HelloAsso (voir App.jsx : la page est rechargée
        entièrement par la redirection HelloAsso, l'état React de la
        soumission initiale est perdu)."""
        inscription = self.client.get_par_token(db, token)
        if inscription is None:
            raise HTTPException(status_code=404, detail="Inscription introuvable")
        return self._vers_sortie(db, inscription)

    def initier_paiement_helloasso(
        self, token: str, donnees: PaiementHelloAssoEntree, db: Session = Depends(get_db)
    ):
        inscription = self.client.get_par_token(db, token)
        if inscription is None:
            raise HTTPException(status_code=404, detail="Inscription introuvable")
        try:
            resultat = self.client.initier_paiement_helloasso(db, token, donnees.retour_url)
        except ValueError as erreur:
            raise HTTPException(status_code=400, detail=str(erreur)) from erreur
        except HelloAssoError as erreur:
            logger.exception("Initiation paiement HelloAsso échouée pour %s", token)
            raise HTTPException(
                status_code=503, detail="Paiement HelloAsso indisponible pour le moment"
            ) from erreur
        return PaiementHelloAssoSortie(redirect_url=resultat["redirect_url"])

    def verifier_paiement_helloasso(self, token: str, db: Session = Depends(get_db)):
        inscription = self.client.verifier_paiement_helloasso(db, token)
        if inscription is None:
            raise HTTPException(status_code=404, detail="Inscription introuvable")
        return self._vers_sortie(db, inscription)

    async def notification_helloasso(self, request: Request, db: Session = Depends(get_db)):
        """Webhook HelloAsso (voir dev.helloasso.com/docs/notifications-webhook)
        — signature non vérifiée (réservée aux comptes "partenaire", pas
        notre cas), donc jamais fait confiance au corps de la requête :
        sert seulement à savoir QUEL checkout intent re-vérifier via
        verifier_paiement_helloasso (source de vérité, un vrai appel
        HelloAsso). Toujours 204, même si le corps est inattendu ou
        l'id introuvable — jamais faire échouer un webhook (HelloAsso
        réessaierait sinon)."""
        try:
            corps = await request.json()
        except Exception:
            return
        checkout_intent_id = (
            corps.get("data", {}).get("checkoutIntentId")
            or corps.get("data", {}).get("order", {}).get("checkoutIntentId")
            or corps.get("checkoutIntentId")
        )
        if checkout_intent_id is None:
            logger.warning("Notification HelloAsso sans checkoutIntentId reconnu : %s", corps)
            return
        self.client.traiter_notification_helloasso(db, checkout_intent_id)

    def dossier_pdf(self, token: str, db: Session = Depends(get_db)):
        inscription = self.client.get_par_token(db, token)
        if inscription is None or not inscription.pdf_dossier_chemin:
            raise HTTPException(status_code=404, detail="Dossier introuvable")
        from .pdf import nom_fichier_dossier
        from .stockage import DOSSIER_INSCRIPTIONS

        chemin = DOSSIER_INSCRIPTIONS / inscription.pdf_dossier_chemin
        if not chemin.exists():
            raise HTTPException(status_code=404, detail="Dossier introuvable")
        # "inline" (pas "attachment") : garde l'ouverture dans un nouvel
        # onglet (voir Confirmation.jsx, <a target="_blank">) — seul le
        # nom proposé si la famille clique ensuite "Enregistrer" change.
        return Response(
            content=chemin.read_bytes(),
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{nom_fichier_dossier(inscription)}"'},
        )

    def facture_pdf(self, token: str, db: Session = Depends(get_db)):
        inscription = self.client.get_par_token(db, token)
        if inscription is None or not inscription.pdf_facture_chemin:
            raise HTTPException(status_code=404, detail="Facture introuvable")
        from .pdf import nom_fichier_facture
        from .stockage import DOSSIER_INSCRIPTIONS

        chemin = DOSSIER_INSCRIPTIONS / inscription.pdf_facture_chemin
        if not chemin.exists():
            raise HTTPException(status_code=404, detail="Facture introuvable")
        return Response(
            content=chemin.read_bytes(),
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{nom_fichier_facture(inscription)}"'},
        )

    def export(self, ecole_id: int, db: Session = Depends(get_db)):
        contenu = self.client.exporter_nouvelles_inscriptions(db, ecole_id)
        if contenu is None:
            raise HTTPException(status_code=404, detail="Aucune nouvelle inscription")
        return Response(
            content=contenu,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=nouvelles_inscriptions.xlsx"},
        )
