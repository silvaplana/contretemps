"""helloasso registrations

Step 8c (spec/modules/helloasso.md §4): each person registered on the
season's HelloAsso campaign (one order item), the member card it became,
its tier, discount code and payments as HelloAsso gives them.

Revision ID: e7a9c1b3d5f8
Revises: a5b7c9d1e3f6
"""

import sqlalchemy as sa
from alembic import op

revision = "e7a9c1b3d5f8"
down_revision = "a5b7c9d1e3f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # deploy.sh runs create_all before Alembic: the table may already exist.
    if "helloasso_registrations" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "helloasso_registrations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.Integer, sa.ForeignKey("ecoles.id"), nullable=False),
        sa.Column("season_id", sa.Integer, sa.ForeignKey("saisons.id"), nullable=False, index=True),
        sa.Column("item_id", sa.String(40), nullable=False),
        sa.Column("order_id", sa.String(40), nullable=False),
        sa.Column("member_id", sa.Integer, sa.ForeignKey("comptes.id"), nullable=True, index=True),
        sa.Column("first_name", sa.String(255), nullable=False),
        sa.Column("last_name", sa.String(255), nullable=False),
        sa.Column("payer_email", sa.String(255), nullable=True),
        sa.Column("tier_name", sa.String(255), nullable=False),
        sa.Column("amount", sa.Integer, nullable=False),
        sa.Column("discount_code", sa.String(100), nullable=True),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("order_date", sa.String(40), nullable=True),
        sa.Column("payments", sa.JSON, nullable=False),
        sa.Column("gone_at", sa.DateTime, nullable=True),
        sa.Column("synced_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("season_id", "item_id"),
    )


def downgrade() -> None:
    op.drop_table("helloasso_registrations")
