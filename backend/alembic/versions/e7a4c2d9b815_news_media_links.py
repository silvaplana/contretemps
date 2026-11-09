"""news: a link (YouTube or any site) in the carousel

spec/modules/actualites.md §3.3 (Seb, 9 November): a carousel element can be
a link. Two nullable columns on news_media, its address and its title; the
site's picture is kept as a photo (photo_sha), so storage and clean-up stay
as they are.

Revision ID: e7a4c2d9b815
Revises: d5f2b8c1e604
Create Date: 2026-11-09 10:20:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7a4c2d9b815'
down_revision: Union[str, Sequence[str], None] = 'd5f2b8c1e604'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `create_all` may have added them already (see the "has_table" pitfall).
    colonnes = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('news_media')}
    with op.batch_alter_table('news_media') as batch:
        if 'link_url' not in colonnes:
            batch.add_column(sa.Column('link_url', sa.String(length=2000), nullable=True))
        if 'link_title' not in colonnes:
            batch.add_column(sa.Column('link_title', sa.String(length=300), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('news_media') as batch:
        batch.drop_column('link_title')
        batch.drop_column('link_url')
