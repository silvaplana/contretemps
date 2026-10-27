"""Groupes du core (spec/core.md §5) : tables `groups` et `group_members`.

Un groupe réunit des fiches sous un nom, pour une organisation et une saison
(ou « permanent », `season_id` vide). Les groupes d'un module ont un parent,
un seul niveau : Bureau › Président·e… Pas de colonne « nature » : `key`
désigne les groupes que le code connaît (« board », « board.president »),
vide pour un groupe créé à la main.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Group(Base):
    __tablename__ = "groups"
    __table_args__ = (Index("ix_groups_org_season_key", "org_id", "season_id", "key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id"), nullable=False, index=True)
    season_id: Mapped[int | None] = mapped_column(ForeignKey("saisons.id"), nullable=True, index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"), nullable=True, index=True)
    key: Mapped[str | None] = mapped_column(String(60), nullable=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)

    # Seulement pour que SQLAlchemy écrive un parent avant ses sous-groupes
    # et les supprime après eux (sauvegarde technique, ecoles/backup_technique.py).
    parent: Mapped["Group | None"] = relationship("Group", remote_side="Group.id")


class GroupMember(Base):
    __tablename__ = "group_members"

    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("comptes.id"), primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
