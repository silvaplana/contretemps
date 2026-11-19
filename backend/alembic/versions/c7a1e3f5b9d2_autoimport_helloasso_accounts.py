"""autoimport: accounts of the HelloAsso formulas

Import auto pièces, step 6 (spec/modules/import-auto-pieces.md §4.2): the
treasurer says once which sales account each HelloAsso formula goes to.

Revision ID: c7a1e3f5b9d2
Revises: ebe5ff66e236
"""

import sqlalchemy as sa
from alembic import op

revision = "c7a1e3f5b9d2"
down_revision = "ebe5ff66e236"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("autoimport_rules")}
    # deploy.sh runs create_all before Alembic: the column may exist already.
    if "helloasso_accounts" not in columns:
        with op.batch_alter_table("autoimport_rules") as batch:
            batch.add_column(sa.Column("helloasso_accounts", sa.JSON, nullable=False, server_default="{}"))


def downgrade() -> None:
    with op.batch_alter_table("autoimport_rules") as batch:
        batch.drop_column("helloasso_accounts")
