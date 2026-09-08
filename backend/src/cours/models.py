"""Tables des cours (voir spec/SPEC.md §6.5). Les relations profs/élèves
sont des tables de jointure, pas des listes stockées sur `cours`.
"""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column

from db import Base

# Plusieurs profs possibles par cours, plusieurs cours possibles par prof.
cours_professeurs = Table(
    "cours_professeurs",
    Base.metadata,
    Column("cours_id", ForeignKey("cours.id"), primary_key=True),
    Column("professeur_id", ForeignKey("comptes.id"), primary_key=True),
)

# Élèves inscrits à un cours — relation "large" (tous les inscrits), pas
# forcément tous participants à une chorégraphie donnée (voir §6.7).
eleves_cours = Table(
    "eleves_cours",
    Base.metadata,
    Column("eleve_id", ForeignKey("comptes.id"), primary_key=True),
    Column("cours_id", ForeignKey("cours.id"), primary_key=True),
)


class Cours(Base):
    __tablename__ = "cours"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecole_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id"), nullable=False, index=True)
    # texte libre, pas un enum fermé (voir §6.5 : permet d'ajouter un
    # nouveau type de cours plus tard sans migration).
    nom: Mapped[str] = mapped_column(String(150), nullable=False)
    jour: Mapped[str | None] = mapped_column(String(20), nullable=True)
    heure_debut: Mapped[str | None] = mapped_column(String(10), nullable=True)
    heure_fin: Mapped[str | None] = mapped_column(String(10), nullable=True)
    salle: Mapped[str | None] = mapped_column(String(50), nullable=True)
    descriptif: Mapped[str | None] = mapped_column(Text, nullable=True)
