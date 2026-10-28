"""seasons: an old season can be opened for edits

Revision ID: 9b40dd3662ca
Revises: f1a3c5e7b9d0
Create Date: 2026-10-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9b40dd3662ca"
down_revision: str | Sequence[str] | None = "f1a3c5e7b9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    colonnes = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("saisons")}
    if "ouverte" in colonnes:
        return
    with op.batch_alter_table("saisons") as batch:
        batch.add_column(sa.Column("ouverte", sa.Boolean, nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("saisons") as batch:
        batch.drop_column("ouverte")
