"""season_helloasso: how the season uses HelloAsso

spec/modules/helloasso.md §8 (step 11): « HelloAsso fait tout » (master, the
campaign) or « L'appli fait tout, HelloAsso encaisse » (payment, no campaign:
empty form columns, card payments use the school's keys). No row: without
HelloAsso. Existing rows are campaigns, so they read "master".

Revision ID: c1b18c1cfaa9
Revises: ab41da4bb0f7
"""

import sqlalchemy as sa
from alembic import op

revision = "c1b18c1cfaa9"
down_revision = "ab41da4bb0f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # deploy.sh runs create_all before Alembic: check the column first.
    colonnes = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("season_helloasso")}
    if "mode" not in colonnes:
        # Plain ADD COLUMN with a constant default: no table rebuild.
        op.add_column("season_helloasso", sa.Column("mode", sa.String(20), nullable=False, server_default="master"))


def downgrade() -> None:
    with op.batch_alter_table("season_helloasso") as table:
        table.drop_column("mode")
