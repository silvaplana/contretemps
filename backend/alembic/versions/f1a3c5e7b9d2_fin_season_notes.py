"""fin_season_notes: the treasurer's one-line explanation of an account's change

financier.md §8.10 step 6 (Seb, 9 November 2026): a gap of more than 30 % with
the previous season is flagged until explained; the written report reuses it.

Revision ID: f1a3c5e7b9d2
Revises: e5b7c9d1f3a6
Create Date: 2026-11-10 02:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f1a3c5e7b9d2'
down_revision: Union[str, Sequence[str], None] = 'e5b7c9d1f3a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("fin_season_notes"):
        return
    op.create_table(
        "fin_season_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("season_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.String(length=10), nullable=False),
        sa.Column("note", sa.String(length=300), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("org_id", "season_id", "number"),
    )
    op.create_index("ix_fin_season_notes_org_id", "fin_season_notes", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_fin_season_notes_org_id", table_name="fin_season_notes")
    op.drop_table("fin_season_notes")
