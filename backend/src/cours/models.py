"""Tables des cours (voir spec/SPEC.md §6.5). Les relations profs/élèves
sont des tables de jointure, pas des listes stockées sur `cours`.
"""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    # Voir spec §2.6 ; rempli automatiquement, voir saisons/automatique.py.
    saison_id: Mapped[int] = mapped_column(ForeignKey("saisons.id"), nullable=False, index=True)
    # texte libre, pas un enum fermé (voir §6.5 : permet d'ajouter un
    # nouveau type de cours plus tard sans migration).
    nom: Mapped[str] = mapped_column(String(150), nullable=False)
    jour: Mapped[str | None] = mapped_column(String(20), nullable=True)
    heure_debut: Mapped[str | None] = mapped_column(String(10), nullable=True)
    heure_fin: Mapped[str | None] = mapped_column(String(10), nullable=True)
    salle: Mapped[str | None] = mapped_column(String(50), nullable=True)
    descriptif: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Ordre d'affichage (Admin > Cours, formulaire public) — jamais
    # alphabétique (ex. "Éveil" doit rester avant "Class Ini" malgré le
    # tri des lettres) : regroupé par famille (Éveil, puis tous les
    # Classique/Pointes, puis tous les Jazz, puis tous les Street, puis
    # tous les Contempo). Auto-calculé à la création (voir cours.py :
    # max existant + 1, un nouveau cours va à la fin) — jamais fourni
    # par le formulaire de création, seulement modifiable a posteriori.
    ordre: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Créneaux EN PLUS du créneau principal ci-dessus (jour/heure_debut/
    # heure_fin) — rare (voir spec/SPEC.md §6.5), ex. "Éveil" proposé le
    # lundi ET le mercredi. Le créneau principal reste inchangé partout
    # ailleurs dans l'appli (planning, présences...) ; ceci ne s'ajoute
    # qu'à l'affichage (voir Admin > Cours et le formulaire public
    # d'inscription).
    horaires_supplementaires: Mapped[list["CoursHoraireSupplementaire"]] = relationship(
        "CoursHoraireSupplementaire",
        cascade="all, delete-orphan",
        order_by="CoursHoraireSupplementaire.id",
    )


class CoursHoraireSupplementaire(Base):
    __tablename__ = "cours_horaires_supplementaires"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cours_id: Mapped[int] = mapped_column(ForeignKey("cours.id"), nullable=False, index=True)
    jour: Mapped[str] = mapped_column(String(20), nullable=False)
    heure_debut: Mapped[str] = mapped_column(String(10), nullable=False)
    heure_fin: Mapped[str] = mapped_column(String(10), nullable=False)
