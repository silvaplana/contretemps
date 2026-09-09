"""Tables des chorégraphies (voir spec/SPEC.md §6.7)."""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column

from db import Base

# Sous-ensemble des élèves du cours lié — table dédiée, distincte de
# `eleves_cours` (voir §6.7 : "une chorégraphie ne rassemble pas
# forcément tous les élèves du cours lié").
choregraphies_eleves = Table(
    "choregraphies_eleves",
    Base.metadata,
    Column("choregraphie_id", ForeignKey("choregraphies.id"), primary_key=True),
    Column("eleve_id", ForeignKey("comptes.id"), primary_key=True),
)


class Choregraphie(Base):
    __tablename__ = "choregraphies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cours_id: Mapped[int] = mapped_column(ForeignKey("cours.id"), nullable=False, index=True)
    nom: Mapped[str] = mapped_column(String(150), nullable=False)
    horaire_repetition: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Un seul costume pour toute la chorégraphie (voir §6.7).
    costume: Mapped[str | None] = mapped_column(Text, nullable=True)
