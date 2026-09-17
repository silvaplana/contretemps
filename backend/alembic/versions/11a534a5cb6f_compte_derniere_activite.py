"""compte derniere activite

Revision ID: 11a534a5cb6f
Revises: ee1cff17d8d9
Create Date: 2026-09-17 01:46:36.497126

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '11a534a5cb6f'
down_revision: Union[str, Sequence[str], None] = 'ee1cff17d8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('comptes', sa.Column('derniere_activite_le', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('comptes', 'derniere_activite_le')
