"""finances: bank connection (Enable Banking), bank balance on accounts

Revision ID: f1a3c5e7b9d0
Revises: e7a9c1b3d5f8
Create Date: 2026-10-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f1a3c5e7b9d0"
down_revision: str | Sequence[str] | None = "e7a9c1b3d5f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspection = sa.inspect(op.get_bind())
    # deploy.sh runs create_all before Alembic: tables and columns may already exist.
    colonnes = {c["name"] for c in inspection.get_columns("fin_accounts")}
    with op.batch_alter_table("fin_accounts") as batch:
        if "bank_uid" not in colonnes:
            batch.add_column(sa.Column("bank_uid", sa.String(100), nullable=True))
        if "bank_balance" not in colonnes:
            batch.add_column(sa.Column("bank_balance", sa.Integer, nullable=True))
        if "bank_balance_date" not in colonnes:
            batch.add_column(sa.Column("bank_balance_date", sa.Date, nullable=True))
    if "fin_bank_connections" in inspection.get_table_names():
        return
    op.create_table(
        "fin_bank_connections",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.Integer, nullable=False, index=True),
        sa.Column("bank", sa.String(120), nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("psu_type", sa.String(20), nullable=False),
        sa.Column("session_encrypted", sa.Text, nullable=True),
        sa.Column("valid_until", sa.DateTime, nullable=True),
        sa.Column("accounts", sa.JSON, nullable=False),
        sa.Column("state", sa.String(64), nullable=True, unique=True),
        sa.Column("state_at", sa.DateTime, nullable=True),
        sa.Column("pending", sa.JSON, nullable=True),
        sa.Column("connected_by", sa.Integer, nullable=True),
        sa.Column("connected_at", sa.DateTime, nullable=True),
        sa.Column("last_sync_at", sa.DateTime, nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.UniqueConstraint("org_id", name="uq_fin_bank_connections_org"),
    )


def downgrade() -> None:
    op.drop_table("fin_bank_connections")
    with op.batch_alter_table("fin_accounts") as batch:
        batch.drop_column("bank_balance_date")
        batch.drop_column("bank_balance")
        batch.drop_column("bank_uid")
