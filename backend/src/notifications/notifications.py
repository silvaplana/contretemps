"""Notifications push (Web Push, voir spec/SPEC.md §8) : un compte abonné
(voir models.py: PushSubscription, un ou plusieurs abonnements par compte
— un par appareil/navigateur) reçoit une vraie notification système même
si l'appli/l'onglet est fermé — ce qu'aucun mécanisme précédent (SSE
compris, voir messagerie/evenements.py) ne permet.

⚠️ Contrairement au SSE : ceci parle à un service TIERS (FCM, Mozilla Push
Service...), pas seulement entre le frontend et ce backend — c'est pour
ça qu'il faut chiffrer (voir pywebpush) et signer (VAPID) chaque envoi.

Sans clés VAPID configurées (voir .env.example), le service est
silencieusement désactivé (`actif` == False) : abonner()/envoyer_a_compte()
ne font rien de cassé, juste rien d'utile — pratique en dev/tests sans
config, et n'empêche jamais le reste de l'appli de fonctionner (envoyer un
message ne doit jamais échouer parce qu'une notification n'a pas pu partir).
"""

from __future__ import annotations

import json
import logging
import os

from pywebpush import WebPushException, webpush
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import PushSubscription

logger = logging.getLogger(__name__)

# Durée (secondes) pendant laquelle le SERVEUR DE PUSH (FCM/Mozilla/...,
# pas nous) garde le message en attente si l'appareil n'est pas joignable
# tout de suite (éteint, hors réseau...) — `ttl=0`, le défaut de
# pywebpush, dirait au contraire "ne le garde pas, tant pis" : un message
# envoyé pendant que le destinataire est hors ligne serait perdu pour de
# bon (signalé). 24h : cohérent avec le délai de relance par mail
# (§5.5, voir messagerie/messages.py: relancer_messages_non_lus) — passé
# ce délai, le message part par mail de toute façon.
TTL_SECONDES = 24 * 60 * 60


class Notifications:
    def __init__(self) -> None:
        self.cle_privee = os.environ.get("VAPID_PRIVATE_KEY")
        self.cle_publique = os.environ.get("VAPID_PUBLIC_KEY")
        self.sujet = os.environ.get("VAPID_SUBJECT", "mailto:admin@silvaplana.cloud")
        self.actif = bool(self.cle_privee and self.cle_publique)

    def abonnements_du_compte(self, db: Session, compte_id: int) -> list[PushSubscription]:
        return list(
            db.scalars(select(PushSubscription).where(PushSubscription.compte_id == compte_id))
        )

    def abonner(
        self, db: Session, compte_id: int, endpoint: str, cle_p256dh: str, cle_auth: str
    ) -> PushSubscription:
        """`endpoint` identifie l'abonnement de façon unique (voir
        models.py) : un appareil qui active les notifications une 2e fois
        (ex. après avoir réinstallé le service worker) retombe en général
        sur le même endpoint — on met juste à jour ses clés plutôt que
        d'accumuler des doublons inutiles."""
        existant = db.scalar(
            select(PushSubscription).where(PushSubscription.endpoint == endpoint)
        )
        if existant is not None:
            existant.compte_id = compte_id
            existant.cle_p256dh = cle_p256dh
            existant.cle_auth = cle_auth
            db.commit()
            db.refresh(existant)
            return existant
        abonnement = PushSubscription(
            compte_id=compte_id, endpoint=endpoint, cle_p256dh=cle_p256dh, cle_auth=cle_auth
        )
        db.add(abonnement)
        db.commit()
        db.refresh(abonnement)
        return abonnement

    def desabonner(self, db: Session, endpoint: str) -> bool:
        abonnement = db.scalar(
            select(PushSubscription).where(PushSubscription.endpoint == endpoint)
        )
        if abonnement is None:
            return False
        db.delete(abonnement)
        db.commit()
        return True

    def envoyer_a_compte(self, db: Session, compte_id: int, titre: str, corps: str) -> None:
        """Envoie la notification à TOUS les abonnements de ce compte
        (tous ses appareils/navigateurs). Un abonnement en échec (le
        principal cas normal : `410 Gone`/`404`, l'utilisateur a désinstallé
        ou révoqué les notifications côté navigateur — voir MDN Push API)
        est supprimé silencieusement ; les autres échecs sont juste
        journalisés — jamais remontés à l'appelant (voir docstring du
        module : ne doit jamais faire échouer l'envoi d'un message)."""
        if not self.actif:
            return
        for abonnement in self.abonnements_du_compte(db, compte_id):
            subscription_info = {
                "endpoint": abonnement.endpoint,
                "keys": {"p256dh": abonnement.cle_p256dh, "auth": abonnement.cle_auth},
            }
            try:
                webpush(
                    subscription_info=subscription_info,
                    data=json.dumps({"title": titre, "body": corps}),
                    vapid_private_key=self.cle_privee,
                    vapid_claims={"sub": self.sujet},
                    ttl=TTL_SECONDES,
                )
            except WebPushException as err:
                statut = getattr(err.response, "status_code", None)
                if statut in (404, 410):
                    db.delete(abonnement)
                    db.commit()
                else:
                    logger.warning("Envoi notification push échoué (compte %s) : %s", compte_id, err)
