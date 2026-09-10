"""Table des abonnements aux notifications push (Web Push, voir
spec/SPEC.md §8 et notifications.py). Un compte peut avoir PLUSIEURS
abonnements à la fois (un par appareil/navigateur où il a activé les
notifications, voir spec §2.1 : plusieurs profils/appareils possibles).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    compte_id: Mapped[int] = mapped_column(ForeignKey("comptes.id"), nullable=False, index=True)
    # Les 3 champs d'un objet PushSubscription JS (voir
    # PushSubscription.toJSON() côté navigateur) — endpoint identifie de
    # façon unique l'abonnement (un même appareil/navigateur qui se
    # réabonne obtient en général le même endpoint, voir upsert() ci-dessous
    # côté notifications.py), les 2 clés servent au chiffrement (voir
    # pywebpush).
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    cle_p256dh: Mapped[str] = mapped_column(String(255), nullable=False)
    cle_auth: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
