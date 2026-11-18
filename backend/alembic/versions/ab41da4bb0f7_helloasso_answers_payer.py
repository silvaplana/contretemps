"""helloasso registrations: answers and payer name

Step 5 of spec/modules/helloasso.md §7.11: the members table and card of a
season imposed by HelloAsso show the photo, the uploaded documents, the
answers and the payer. A JSON column and a text column, filled by the
next synchronisation (every 5 minutes); existing rows read an empty list.

Revision ID: ab41da4bb0f7
Revises: 44e222e7884c
"""

import sqlalchemy as sa
from alembic import op

revision = "ab41da4bb0f7"
down_revision = "44e222e7884c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # deploy.sh runs create_all before Alembic: check the columns first.
    colonnes = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("helloasso_registrations")}
    if "answers" not in colonnes:
        op.add_column(
            "helloasso_registrations", sa.Column("answers", sa.JSON, nullable=False, server_default="[]")
        )
    if "payer_name" not in colonnes:
        op.add_column("helloasso_registrations", sa.Column("payer_name", sa.String(255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("helloasso_registrations") as table:
        table.drop_column("payer_name")
        table.drop_column("answers")
