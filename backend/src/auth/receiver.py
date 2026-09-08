"""Routes REST de connexion et de bascule de profil famille (voir spec
§2.2). Aucune notion de session/token pour l'instant — juste l'identité du
compte trouvé, la vraie gestion de session est un point ouvert (voir
spec/SPEC.md section 8).
"""

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from db import get_db

from .auth import Auth
from .schemas import CompteConnecte, Connexion, DemandeBascule, ConfirmationBascule, ReponseBascule


class AuthReceiver:
    def __init__(self, client: Auth, app: FastAPI) -> None:
        self.client = client
        self.app = app
        self._register_routes()

    def _register_routes(self) -> None:
        self.app.post("/auth/login", response_model=CompteConnecte)(self.login)
        self.app.post("/auth/bascule/verifier", response_model=ReponseBascule)(
            self.verifier_bascule
        )
        self.app.post("/auth/bascule/confirmer", response_model=CompteConnecte)(
            self.confirmer_bascule
        )

    def login(self, donnees: Connexion, db: Session = Depends(get_db)):
        compte = self.client.connecter(db, donnees.ecole_id, donnees.identifiant, donnees.code)
        if compte is None:
            raise HTTPException(status_code=401, detail="Identifiant ou code incorrect")
        return compte

    def verifier_bascule(self, donnees: DemandeBascule, db: Session = Depends(get_db)):
        """Le frontend appelle ça avant de basculer : si code_requis est
        faux, il bascule tout de suite (voir §2.2, switch libre vers un
        rôle égal ou inférieur)."""
        code_requis = self.client.demander_code_pour_bascule(
            db, donnees.depuis_compte_id, donnees.vers_compte_id
        )
        return {"code_requis": code_requis}

    def confirmer_bascule(self, donnees: ConfirmationBascule, db: Session = Depends(get_db)):
        if not self.client.verifier_code_bascule(db, donnees.vers_compte_id, donnees.code):
            raise HTTPException(status_code=401, detail="Code incorrect")
        compte = self.client.comptes.get(db, donnees.vers_compte_id)
        if compte is None:
            raise HTTPException(status_code=404, detail="Compte introuvable")
        return compte
