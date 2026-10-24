"""ecoles: vocabulary

Words a school shows instead of « École », « Élèves » and « Cours » (Seb,
24/10; spec/SPEC.md §5.1.1). Empty means the default word. The backend's
create_all runs before `alembic upgrade head` in deploy.sh but never adds a
column to an existing table: only the missing columns are added.

Revision ID: d8f0b2c4e6a7
Revises: c7e9a1b3d5f8
"""

import sqlalchemy as sa
from alembic import op

revision = "d8f0b2c4e6a7"
down_revision = "c7e9a1b3d5f8"
branch_labels = None
depends_on = None

COLUMNS = ("mot_ecole", "mot_eleves", "mot_cours")


def upgrade() -> None:
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("ecoles")}
    with op.batch_alter_table("ecoles") as batch:
        for name in COLUMNS:
            if name not in existing:
                batch.add_column(sa.Column(name, sa.String(length=30), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ecoles") as batch:
        for name in COLUMNS:
            batch.drop_column(name)
