"""school nature: ties each school to a brand (Contretemps, Assofight)

New column `ecoles.nature`, "danse" for every existing school, so nothing
changes for Contretemps (Seb 17/11/2026). A Super User switches a school to
"combat" from Admin > École > Personnalisation; its address then moves to the
Assofight domain (spec/core.md §2.7 bis).

Revision ID: 44e222e7884c
Revises: e36ccfe307ce
"""

import sqlalchemy as sa
from alembic import op

revision = "44e222e7884c"
down_revision = "e36ccfe307ce"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # deploy.sh runs create_all before Alembic: create_all never adds a column
    # to an existing table, but check anyway, like the other migrations.
    colonnes = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("ecoles")}
    if "nature" not in colonnes:
        # Plain ADD COLUMN (SQLite accepts NOT NULL with a constant default):
        # no table rebuild, every existing row reads "danse".
        op.add_column("ecoles", sa.Column("nature", sa.String(20), nullable=False, server_default="danse"))


def downgrade() -> None:
    with op.batch_alter_table("ecoles") as table:
        table.drop_column("nature")
