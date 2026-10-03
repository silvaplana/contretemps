"""Tables des chorégraphies (voir spec/SPEC.md §6.7)."""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column

from db import Base

# Élèves participants : choisis parmi TOUS les élèves de l'école (décision
# du 2026-10-03), pas seulement ceux du cours lié.
choregraphies_eleves = Table(
    "choregraphies_eleves",
    Base.metadata,
    Column("choregraphie_id", ForeignKey("choregraphies.id"), primary_key=True),
    Column("eleve_id", ForeignKey("comptes.id"), primary_key=True),
)

# Vidéos d'une chorégraphie, dans l'ordre choisi. C'est la chorégraphie qui
# référence ses vidéos : le module `videos`, générique, ne sait rien d'elle
# (voir videos/models.py). Une vidéo n'appartient qu'à une chorégraphie.
choregraphies_videos = Table(
    "choregraphies_videos",
    Base.metadata,
    Column("choregraphie_id", ForeignKey("choregraphies.id"), nullable=False, index=True),
    Column("video_id", ForeignKey("videos.id"), primary_key=True),
    Column("ordre", Integer, nullable=False, default=0),
)


class Choregraphie(Base):
    __tablename__ = "choregraphies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Le cours auquel la chorégraphie est associée dès sa création : il
    # désigne les professeurs qui peuvent la gérer (spec §5.3).
    cours_id: Mapped[int] = mapped_column(ForeignKey("cours.id"), nullable=False, index=True)
    nom: Mapped[str] = mapped_column(String(150), nullable=False)
    horaire_repetition: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Un seul costume pour toute la chorégraphie (voir §6.7).
    costume: Mapped[str | None] = mapped_column(Text, nullable=True)
