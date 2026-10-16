"""Plafond mensuel de l'assistant par école (Seb, 16 octobre).

Revision ID: a1c3e5f7b9d2
Revises: e5c7a9b1d3f4
"""

import sqlalchemy as sa
from alembic import op

revision = "a1c3e5f7b9d2"
down_revision = "e5c7a9b1d3f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    colonnes = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("ecoles")}
    if "assistant_plafond_mensuel_usd" not in colonnes:
        with op.batch_alter_table("ecoles") as batch:
            batch.add_column(
                sa.Column("assistant_plafond_mensuel_usd", sa.Float(), nullable=False, server_default="10")
            )


def downgrade() -> None:
    with op.batch_alter_table("ecoles") as batch:
        batch.drop_column("assistant_plafond_mensuel_usd")
