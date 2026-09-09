"""Table des vidéos (voir spec/SPEC.md §6.8)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cours_id: Mapped[int] = mapped_column(ForeignKey("cours.id"), nullable=False, index=True)
    choregraphie_id: Mapped[int | None] = mapped_column(
        ForeignKey("choregraphies.id"), nullable=True, index=True
    )
    nom: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Chemin/URL, pas le fichier lui-même (voir §6.8).
    lien_fichier: Mapped[str] = mapped_column(String(500), nullable=False)
    # Vignette (chemin relatif, même convention que lien_fichier, voir
    # videos/stockage.py) — absente de la spec §6.8 d'origine : ajoutée
    # parce que les navigateurs mobiles (Chrome/Brave/Samsung Internet
    # Android testés) n'affichent PAS la 1re image d'une vidéo tant
    # qu'elle n'est pas jouée (juste une case noire + icône "média"),
    # contrairement à Chrome desktop — sans vignette, l'écran Vidéo
    # paraît cassé sur mobile alors que la lecture elle-même fonctionne.
    poster: Mapped[str | None] = mapped_column(String(500), nullable=True)
    date_publication: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("comptes.id"), nullable=False)
    # Ordre manuel, utilisé uniquement dans le contexte d'une chorégraphie
    # (voir §6.8 : ignoré sur l'écran Vidéo, trié par date_publication là-bas).
    ordre: Mapped[int | None] = mapped_column(Integer, nullable=True)
