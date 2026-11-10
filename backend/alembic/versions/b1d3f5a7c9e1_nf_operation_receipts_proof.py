"""nf_operation_receipts: the transfer notice kept on a bank transaction without invoice

notes-de-frais.md §7 octies (Seb, 10 November 2026): a transfer notice that
pays no known invoice stays on its bank transaction (file in Docs ›
Financier › VIREMENTS SANS FACTURE) until the invoice arrives and adopts it.

Revision ID: b1d3f5a7c9e1
Revises: a9c1e3f5b7d9
Create Date: 2026-11-10 16:10:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b1d3f5a7c9e1'
down_revision: Union[str, Sequence[str], None] = 'a9c1e3f5b7d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    existantes = {c['name'] for c in sa.inspect(bind).get_columns('nf_operation_receipts')}
    with op.batch_alter_table('nf_operation_receipts') as batch:
        if 'proof_doc_node_id' not in existantes:
            batch.add_column(sa.Column('proof_doc_node_id', sa.Integer(), nullable=True))
        if 'proof_name' not in existantes:
            batch.add_column(sa.Column('proof_name', sa.String(length=200), nullable=True))
        if 'proof_mime' not in existantes:
            batch.add_column(sa.Column('proof_mime', sa.String(length=100), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('nf_operation_receipts') as batch:
        batch.drop_column('proof_mime')
        batch.drop_column('proof_name')
        batch.drop_column('proof_doc_node_id')
