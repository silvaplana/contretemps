"""merge nf deferred gap and choreography music heads

Revision ID: e548f7e05356
Revises: c5e7a9b1d3f5, ff4426b494bd
Create Date: 2026-11-06 18:31:20.878017

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e548f7e05356'
down_revision: Union[str, Sequence[str], None] = ('c5e7a9b1d3f5', 'ff4426b494bd')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
