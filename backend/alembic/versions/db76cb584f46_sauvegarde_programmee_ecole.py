"""sauvegarde programmee ecole

Revision ID: db76cb584f46
Revises: 322661184736
Create Date: 2026-09-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'db76cb584f46'
down_revision: Union[str, Sequence[str], None] = '322661184736'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'ecoles',
        sa.Column('sauvegarde_active', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        'ecoles',
        sa.Column(
            'sauvegarde_periodicite', sa.String(length=20), nullable=False, server_default='semaine'
        ),
    )
    op.add_column('ecoles', sa.Column('sauvegarde_jour_semaine', sa.Integer(), nullable=True))
    op.add_column('ecoles', sa.Column('sauvegarde_heure', sa.String(length=5), nullable=True))
    op.add_column(
        'ecoles', sa.Column('sauvegarde_derniere_execution', sa.DateTime(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('ecoles', 'sauvegarde_derniere_execution')
    op.drop_column('ecoles', 'sauvegarde_heure')
    op.drop_column('ecoles', 'sauvegarde_jour_semaine')
    op.drop_column('ecoles', 'sauvegarde_periodicite')
    op.drop_column('ecoles', 'sauvegarde_active')
