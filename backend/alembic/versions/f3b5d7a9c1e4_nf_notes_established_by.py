"""Who established a piece from Financier › Pièces (notes-de-frais.md §7 quinquies)

Revision ID: f3b5d7a9c1e4
Revises: e5a1c3d7f9b2
Create Date: 2026-10-31

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f3b5d7a9c1e4"
down_revision: str | Sequence[str] | None = "e5a1c3d7f9b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # deploy.sh runs create_all before Alembic: the column may already exist.
    if "established_by" in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("nf_notes")}:
        return
    with op.batch_alter_table("nf_notes") as batch:
        batch.add_column(sa.Column("established_by", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("nf_notes") as batch:
        batch.drop_column("established_by")
