"""Tables of the FFST module (spec/modules/ffst.md §7): the club login on the
FFST site (password encrypted, securite/chiffrement.py), and the copy of the
last reading of the site's three lists. No licence table of our own: the
site stays the only reference."""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FfstConnection(Base):
    __tablename__ = "ffst_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id"), nullable=False, unique=True)
    # The club login, typed in three boxes on the site (e.g. 21 / 13 / 1230).
    login_part1: Mapped[str] = mapped_column(String(20), nullable=False)
    login_part2: Mapped[str] = mapped_column(String(20), nullable=False)
    login_part3: Mapped[str] = mapped_column(String(20), nullable=False)
    password_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    connected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_test_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class FfstSnapshot(Base):
    """One list as last read on the site (`licensees`, `validated`, `drafts`),
    rows kept as the site gives them; replaced whole at each reading."""

    __tablename__ = "ffst_snapshots"
    __table_args__ = (UniqueConstraint("org_id", "list_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id"), nullable=False)
    list_name: Mapped[str] = mapped_column(String(20), nullable=False)
    rows: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    read_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
