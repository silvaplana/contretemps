"""Relevé des opérations d'IA payantes (voir spec/SPEC.md §5.1.1, section
« Usage ressources et IA de la saison », demande du 2026-10-15) : une ligne
par opération, avec son coût et son poste (lecture d'une fiche
d'inscription, détourage d'un logo...)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ConsommationIA(Base):
    __tablename__ = "consommations_ia"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecole_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id"), nullable=False, index=True)
    # Voir spec §2.6 ; rempli automatiquement, voir saisons/automatique.py.
    saison_id: Mapped[int] = mapped_column(ForeignKey("saisons.id"), nullable=False, index=True)
    # Poste de dépense, voir ressources.py:CATEGORIES_IA.
    categorie: Mapped[str] = mapped_column(String(50), nullable=False)
    cout_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    detail: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cree_le: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
