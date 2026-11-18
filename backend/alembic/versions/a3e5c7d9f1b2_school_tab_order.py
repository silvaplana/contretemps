"""school tab order: one bottom bar order for the whole school

`ecoles.tab_order` (JSON list of tab keys, null = the module list order),
set in Admin > School > Fonctionnalités (Seb 18/11/2026). It replaces the
per-person order of Profil > Ma barre du bas; `comptes.tab_order` stays,
unused.

Revision ID: a3e5c7d9f1b2
Revises: 9f819abbd000
"""

import sqlalchemy as sa
from alembic import op

revision = "a3e5c7d9f1b2"
down_revision = "9f819abbd000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    colonnes = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("ecoles")}
    if "tab_order" not in colonnes:
        op.add_column("ecoles", sa.Column("tab_order", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ecoles") as table:
        table.drop_column("tab_order")
