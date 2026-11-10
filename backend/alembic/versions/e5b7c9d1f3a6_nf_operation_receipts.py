"""nf_operation_receipts: bank transactions justified without receipt or with a receipt requested

Revision ID: e5b7c9d1f3a6
Revises: d4f6a8b0c2e4
Create Date: 2026-11-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5b7c9d1f3a6'
down_revision: Union[str, Sequence[str], None] = 'd4f6a8b0c2e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("nf_operation_receipts"):
        return
    op.create_table(
        "nf_operation_receipts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("bank_operation_id", sa.Integer(), nullable=False),
        sa.Column("no_receipt_reason", sa.String(length=200), nullable=True),
        sa.Column("requested_person_id", sa.Integer(), nullable=True),
        sa.Column("requested_at", sa.DateTime(), nullable=True),
        sa.Column("requested_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("org_id", "bank_operation_id"),
    )
    op.create_index("ix_nf_operation_receipts_org_id", "nf_operation_receipts", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_nf_operation_receipts_org_id", table_name="nf_operation_receipts")
    op.drop_table("nf_operation_receipts")
