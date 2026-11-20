"""fin_document_templates

« Comme l'an dernier » keeps last year's layout (financier.md §8.10, step 6,
Seb 20/11): for one spreadsheet of the previous season, the cell → figures
mapping read once by the model.

Revision ID: a9d3f6c20b18
Revises: e5b8c2f41a07
Create Date: 2026-11-20 20:40:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9d3f6c20b18'
down_revision: Union[str, Sequence[str], None] = 'e5b8c2f41a07'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table('fin_document_templates'):
        return
    op.create_table(
        'fin_document_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('node_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('mapping', sa.Text(), nullable=False),
        sa.Column('warnings', sa.Text(), nullable=False),
        sa.Column('cost_usd', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('org_id', 'node_id'),
    )
    op.create_index(op.f('ix_fin_document_templates_org_id'), 'fin_document_templates', ['org_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_fin_document_templates_org_id'), table_name='fin_document_templates')
    op.drop_table('fin_document_templates')
