"""helloasso campaign

Step 8b (spec/modules/helloasso.md §3): the HelloAsso campaign of a season
(`season_helloasso`) and the fields it brings to the member card
(`member_fields.source` = "helloasso", `source_key` = the HelloAsso question).

Revision ID: d5f7b9a1c3e6
Revises: c8e0a2b4d6f1
"""

import sqlalchemy as sa
from alembic import op

revision = "d5f7b9a1c3e6"
down_revision = "c8e0a2b4d6f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    # deploy.sh runs create_all before Alembic: the table may already exist.
    if "season_helloasso" not in inspector.get_table_names():
        op.create_table(
            "season_helloasso",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("org_id", sa.Integer, sa.ForeignKey("ecoles.id"), nullable=False),
            sa.Column("season_id", sa.Integer, sa.ForeignKey("saisons.id"), nullable=False, unique=True),
            sa.Column("form_type", sa.String(30), nullable=False),
            sa.Column("form_slug", sa.String(255), nullable=False),
            sa.Column("form_name", sa.String(255), nullable=False),
            sa.Column("chosen_at", sa.DateTime, nullable=False),
            sa.Column("synced_at", sa.DateTime, nullable=True),
        )
    columns = {c["name"] for c in inspector.get_columns("member_fields")}
    with op.batch_alter_table("member_fields") as batch:
        if "source" not in columns:
            batch.add_column(sa.Column("source", sa.String(30), nullable=True))
        if "source_key" not in columns:
            batch.add_column(sa.Column("source_key", sa.String(100), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("member_fields") as batch:
        batch.drop_column("source_key")
        batch.drop_column("source")
    op.drop_table("season_helloasso")
