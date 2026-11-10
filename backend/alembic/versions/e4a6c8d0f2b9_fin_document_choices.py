"""fin_document_choices: which of last year's bilan documents are produced again

financier.md §8.10 step 6 (Seb, 10 November 2026): the documents of a season
follow those of the previous season's Bilan financier folder in Docs; the
treasurer ticks them and corrects their nature.

Revision ID: e4a6c8d0f2b9
Revises: b6e2d9f4a1c7
Create Date: 2026-11-10 23:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e4a6c8d0f2b9'
down_revision: Union[str, Sequence[str], None] = 'b6e2d9f4a1c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("fin_document_choices"):
        return
    op.create_table(
        "fin_document_choices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("season_id", sa.Integer(), nullable=False),
        sa.Column("node_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("selected", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_fin_document_choices_org_id", "fin_document_choices", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_fin_document_choices_org_id", table_name="fin_document_choices")
    op.drop_table("fin_document_choices")
