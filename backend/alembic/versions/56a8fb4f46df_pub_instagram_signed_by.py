"""pub_instagram signed_by: the member who signs the relayed Instagram posts

Revision ID: 56a8fb4f46df
Revises: 49d79f526eb1
Create Date: 2026-11-13 15:33:12.321145

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '56a8fb4f46df'
down_revision: Union[str, Sequence[str], None] = '49d79f526eb1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table: str) -> set[str]:
    return {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    # `create_all` may have added them already (see the "has_table" pitfall).
    if 'signed_by' in _columns('pub_instagram'):
        return
    with op.batch_alter_table('pub_instagram') as batch:
        batch.add_column(sa.Column('signed_by', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('signed_by_name', sa.String(length=100), nullable=False, server_default=''))
        batch.create_foreign_key('fk_pub_instagram_signed_by', 'comptes', ['signed_by'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('pub_instagram') as batch:
        batch.drop_constraint('fk_pub_instagram_signed_by', type_='foreignkey')
        batch.drop_column('signed_by_name')
        batch.drop_column('signed_by')
