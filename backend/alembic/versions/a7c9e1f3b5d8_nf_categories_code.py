"""Expense-note categories linked to the chart of accounts (financier.md §8.3 ter)

Revision ID: a7c9e1f3b5d8
Revises: f6b8c0d2e4a7
Create Date: 2026-10-30

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7c9e1f3b5d8"
down_revision: str | Sequence[str] | None = "f6b8c0d2e4a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # deploy.sh runs create_all before Alembic: the column may already exist.
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("nf_categories")}
    if "code" not in columns:
        with op.batch_alter_table("nf_categories") as batch:
            batch.add_column(sa.Column("code", sa.String(length=10), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("nf_categories") as batch:
        batch.drop_column("code")
