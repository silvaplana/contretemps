"""Routes REST des notifications push — reçoit les requêtes HTTP, délègue
tout à Notifications (voir notifications.py).
"""

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from db import get_db

from .notifications import Notifications
from .schemas import AbonnementEntree, ClePubliqueSortie


class NotificationsReceiver:
    def __init__(self, client: Notifications, app: FastAPI) -> None:
        self.client = client
        self.app = app
        self._register_routes()

    def _register_routes(self) -> None:
        self.app.get("/push/cle-publique", response_model=ClePubliqueSortie)(self.cle_publique)
        self.app.post("/comptes/{compte_id}/push/abonnement", status_code=204)(self.abonner)
        self.app.delete("/push/abonnement", status_code=204)(self.desabonner)

    def cle_publique(self):
        return {"cle_publique": self.client.cle_publique if self.client.actif else None}

    def abonner(self, compte_id: int, donnees: AbonnementEntree, db: Session = Depends(get_db)):
        self.client.abonner(
            db, compte_id, donnees.endpoint, donnees.keys.p256dh, donnees.keys.auth
        )

    def desabonner(self, endpoint: str, db: Session = Depends(get_db)):
        self.client.desabonner(db, endpoint)
