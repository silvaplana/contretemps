"""Table `org_modules` (spec/core.md §9 bis.3) : les modules qu'une
organisation a éteints. Pas de ligne = module allumé, pour que les écoles
existantes et les modules ajoutés plus tard soient allumés sans rien écrire.
Éteindre n'efface rien : la ligne passe à `enabled=False`, et rallumer la
remet à True."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OrgModule(Base):
    __tablename__ = "org_modules"

    org_id: Mapped[int] = mapped_column(Integer, ForeignKey("ecoles.id"), primary_key=True)
    module_key: Mapped[str] = mapped_column(String(40), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)
