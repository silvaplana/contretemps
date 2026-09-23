"""Table `saisons` (voir spec/SPEC.md §2.6 et §6.1bis). Une saison est une
année d'activité d'une école ; tout, sauf l'école elle-même, appartient à
une saison. Aucun champ "saison courante" : c'est toujours la plus
récemment créée de l'école (voir saisons.py : saison_courante_id).
"""

from __future__ import annotations

import datetime as dt
from datetime import datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Saison(Base):
    __tablename__ = "saisons"
    __table_args__ = (UniqueConstraint("ecole_id", "nom", name="uq_saison_ecole_nom"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecole_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id"), nullable=False, index=True)
    # Texte libre (ex. "2026-2027"), renommable : rien ne doit en déduire
    # des dates, ce sont date_debut/date_fin qui font foi.
    nom: Mapped[str] = mapped_column(String(50), nullable=False)
    date_debut: Mapped[dt.date] = mapped_column(Date, nullable=False)
    date_fin: Mapped[dt.date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
