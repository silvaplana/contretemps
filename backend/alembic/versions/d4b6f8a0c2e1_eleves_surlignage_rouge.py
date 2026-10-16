"""Élèves : surlignage rouge gardé en base (ligne et colonnes)

Revision ID: d4b6f8a0c2e1
Revises: c7e9a1b3d5f2
Create Date: 2026-10-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd4b6f8a0c2e1'
down_revision: Union[str, Sequence[str], None] = 'c7e9a1b3d5f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    colonnes = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('profils_eleves')}
    if 'ligne_rouge' not in colonnes:
        op.add_column('profils_eleves', sa.Column('ligne_rouge', sa.Boolean(), nullable=False, server_default='0'))
    if 'cellules_rouges' not in colonnes:
        op.add_column('profils_eleves', sa.Column('cellules_rouges', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('profils_eleves', 'cellules_rouges')
    op.drop_column('profils_eleves', 'ligne_rouge')
