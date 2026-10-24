"""ecoles: vocabulary for teachers

Word a school shows instead of « Profs » (Seb, 24/10). Same as the previous
vocabulary columns: only added when missing, since create_all runs first.

Revision ID: e9a1c3d5f7b8
Revises: d8f0b2c4e6a7
"""

import sqlalchemy as sa
from alembic import op

revision = "e9a1c3d5f7b8"
down_revision = "d8f0b2c4e6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("ecoles")}
    if "mot_profs" not in existing:
        with op.batch_alter_table("ecoles") as batch:
            batch.add_column(sa.Column("mot_profs", sa.String(length=30), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ecoles") as batch:
        batch.drop_column("mot_profs")
