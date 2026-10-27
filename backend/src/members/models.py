"""Tables `member_fields` (la fiche : un champ par ligne, par organisation et
par saison) et `member_values` (les réponses, une par fiche et par champ).

Un champ de format « group » n'a pas de réponse ici : cocher un sous-groupe
fait entrer la fiche dans ce groupe (`group_members`).
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from db import Base

# Les formats de la réponse (spec/core.md §4.3), dans l'ordre de la liste.
FORMATS = (
    "short_text", "long_text", "number", "date", "yes_no", "phone", "postal_code", "file", "list", "group",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MemberField(Base):
    __tablename__ = "member_fields"
    __table_args__ = (Index("ix_member_fields_org_season", "org_id", "season_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id"), nullable=False)
    season_id: Mapped[int] = mapped_column(ForeignKey("saisons.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False, default="short_text")
    # Liste déroulante : les choix proposés, dans l'ordre.
    choices: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Format « group » : on coche parmi les sous-groupes de ce groupe.
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"), nullable=True)
    multiple: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Réglages avancés, côté membre seulement (les admins voient tout).
    member_sees: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    member_edits: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    others_see: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Pour qui : vide = tous les membres, sinon seulement ce groupe.
    for_group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"), nullable=True)
    # « Retirer ce champ » : il disparaît de la fiche, ses réponses restent.
    removed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)


class MemberValue(Base):
    __tablename__ = "member_values"

    member_id: Mapped[int] = mapped_column(ForeignKey("comptes.id"), primary_key=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("member_fields.id"), primary_key=True, index=True)
    # Texte, nombre, date ISO, booléen, choix (liste si plusieurs) ou, pour
    # un fichier, {"sha256", "name", "size"}.
    value: Mapped[object] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


class MemberColumn(Base):
    """L'affichage dans Admin (spec/core.md §4.3, niveau 2) : les colonnes du
    tableau des membres, dans l'ordre, affichées ou non. `key` : une colonne
    de l'écran (« cours », « paiement »…) ou « field:<id> » pour un champ de
    la fiche. Pas de ligne pour la saison = l'ordre d'origine, tout affiché."""

    __tablename__ = "member_columns"

    org_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id"), primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("saisons.id"), primary_key=True)
    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    shown: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
