"""choreography music

The music of a choreography (Seb, 2026-11-06): author, title and duration
in seconds, all optional. Existing choreographies get NULL.

Revision ID: ff4426b494bd
Revises: b4d6f8a0c2e4
Create Date: 2026-11-06 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ff4426b494bd'
down_revision: Union[str, Sequence[str], None] = 'b4d6f8a0c2e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNS = ('music_author', 'music_title', 'music_duration_seconds')


def upgrade() -> None:
    # `create_all` may have added them already (see the "has_table" pitfall).
    existing = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('choregraphies')}
    with op.batch_alter_table('choregraphies') as batch:
        if 'music_author' not in existing:
            batch.add_column(sa.Column('music_author', sa.String(length=150), nullable=True))
        if 'music_title' not in existing:
            batch.add_column(sa.Column('music_title', sa.String(length=200), nullable=True))
        if 'music_duration_seconds' not in existing:
            batch.add_column(sa.Column('music_duration_seconds', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('choregraphies') as batch:
        for column in reversed(COLUMNS):
            batch.drop_column(column)
