"""Expense natures, transfer states and payers (financier.md §8.3 bis)

Revision ID: a3c5e7f9b1d2
Revises: 9b40dd3662ca
Create Date: 2026-10-29

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3c5e7f9b1d2"
down_revision: str | Sequence[str] | None = "9b40dd3662ca"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


NOTES = (
    sa.Column("nature", sa.String(length=20), nullable=False, server_default="frais"),
    sa.Column("supplier", sa.String(length=120), nullable=True),
    sa.Column("prepared_at", sa.DateTime(), nullable=True),
    sa.Column("prepared_by", sa.Integer(), nullable=True),
    sa.Column("payer_id", sa.Integer(), nullable=True),
    sa.Column("transfer_sent_at", sa.DateTime(), nullable=True),
    sa.Column("transfer_sent_by", sa.Integer(), nullable=True),
    sa.Column("bank_operation_id", sa.Integer(), nullable=True),
)


def upgrade() -> None:
    inspection = sa.inspect(op.get_bind())
    # deploy.sh runs create_all before Alembic: tables may already exist (not new columns).
    existantes = {c["name"] for c in inspection.get_columns("nf_notes")}
    with op.batch_alter_table("nf_notes") as batch:
        for colonne in NOTES:
            if colonne.name not in existantes:
                batch.add_column(colonne)
    if "doc_node_id" not in {c["name"] for c in inspection.get_columns("nf_pieces")}:
        with op.batch_alter_table("nf_pieces") as batch:
            batch.add_column(sa.Column("doc_node_id", sa.Integer(), nullable=True))
    if "nf_payers" in inspection.get_table_names():
        return
    op.create_table(
        "nf_payers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "person_id", name="uq_nf_payer"),
    )
    op.create_index(op.f("ix_nf_payers_org_id"), "nf_payers", ["org_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_nf_payers_org_id"), table_name="nf_payers")
    op.drop_table("nf_payers")
    with op.batch_alter_table("nf_pieces") as batch:
        batch.drop_column("doc_node_id")
    with op.batch_alter_table("nf_notes") as batch:
        for colonne in ("bank_operation_id", "transfer_sent_by", "transfer_sent_at", "payer_id", "prepared_by",
                        "prepared_at", "supplier", "nature"):
            batch.drop_column(colonne)
