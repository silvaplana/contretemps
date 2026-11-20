"""autoimport: licence part of the HelloAsso formulas

Importation automatique de pièces (spec/modules/import-auto-pieces.md §4.2):
per formula, the licence part (cents) credited to the licences account.

Revision ID: e5b7c9d1f3a2
Revises: d4e8a2c6f1b3
"""

import sqlalchemy as sa
from alembic import op

revision = "e5b7c9d1f3a2"
down_revision = "d4e8a2c6f1b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("autoimport_rules")}
    # deploy.sh runs create_all before Alembic: the column may exist already.
    if "helloasso_licences" not in columns:
        with op.batch_alter_table("autoimport_rules") as batch:
            batch.add_column(sa.Column("helloasso_licences", sa.JSON, nullable=False, server_default="{}"))


def downgrade() -> None:
    with op.batch_alter_table("autoimport_rules") as batch:
        batch.drop_column("helloasso_licences")
