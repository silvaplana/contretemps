"""Routes de l'édition OnlyOffice (voir bureautique.py). `configuration`
demande la session ; `fichier` et `retour` sont appelées par le serveur
OnlyOffice, sans session : protégées par le jeton signé de l'adresse (et,
pour le retour, par la signature d'OnlyOffice)."""

from __future__ import annotations

import logging
from dataclasses import replace

from assistant.receiver import super_user_ou_sa_fiche
from comptes import Compte, rbac
from documents.ports import Member
from documents.service import DocError
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from db import get_db

from .bureautique import Bureautique, jwt_lire


class BureautiqueReceiver:
    def __init__(self, client: Bureautique, app: FastAPI, current_member) -> None:
        self.client = client
        c = client

        @app.get("/bureautique/orgs/{org_id}/nodes/{node_id}/configuration")
        def configuration(
            org_id: int,
            node_id: int,
            request: Request,
            compte: Compte = Depends(rbac.compte_appelant),
            membre: Member = Depends(current_member),
            db: Session = Depends(get_db),
        ):
            if compte is None or not super_user_ou_sa_fiche(db, compte):
                raise HTTPException(status_code=403, detail="L'édition en ligne est en essai : réservée au Super User.")
            if not c.actif:
                raise HTTPException(status_code=503, detail="L'édition en ligne n'est pas configurée sur ce serveur.")
            # Adresse publique de l'API telle que l'appli la voit (adresse de
            # l'école) : OnlyOffice y lit le fichier et y renvoie le résultat.
            base_api = f"https://{request.headers.get('x-forwarded-host') or request.url.hostname}/api"
            try:
                return c.configuration(db, replace(membre, org_id=org_id), compte.id, node_id, base_api)
            except DocError as erreur:
                raise HTTPException(status_code=erreur.status, detail=erreur.message) from erreur
            except ValueError as erreur:
                raise HTTPException(status_code=415, detail=str(erreur)) from erreur

        @app.get("/bureautique/fichier/{jeton}")
        def fichier(jeton: str, db: Session = Depends(get_db)):
            charge = c.lire_jeton(jeton)
            if charge is None:
                raise HTTPException(status_code=403, detail="Lien expiré")
            membre = c.membre_de(db, charge["c"], charge["o"])
            chemin, nom, mime = c.documents.content(db, membre, charge["n"])
            return FileResponse(chemin, media_type=mime, filename=nom)

        @app.post("/bureautique/retour/{jeton}")
        async def retour(jeton: str, request: Request, db: Session = Depends(get_db)):
            charge = c.lire_jeton(jeton)
            if charge is None:
                return {"error": 1}
            corps = await request.json()
            # Signature d'OnlyOffice : dans le corps (token) ou l'en-tête.
            signe = corps.get("token") or request.headers.get("authorization", "").removeprefix("Bearer ").strip()
            contenu = jwt_lire(signe, c.secret) if signe else None
            if contenu is None:
                return {"error": 1}
            contenu = contenu.get("payload", contenu)
            try:
                c.retour(db, charge, contenu)
            except Exception:  # OnlyOffice réessaie si on répond une erreur
                logging.getLogger(__name__).exception("OnlyOffice : retour impossible")
                return {"error": 1}
            return {"error": 0}
