"""news media: photo, video, document

Step 2 of the news module (spec/modules/actualites.md §7): an item may carry
one photo or one video, and one Docs file. Three nullable columns on
news_items; nothing existing changes.

Revision ID: a7d3e91c4b20
Revises: c0573245638d
Create Date: 2026-11-07 00:10:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7d3e91c4b20'
down_revision: Union[str, Sequence[str], None] = 'c0573245638d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `create_all` may have added them already (see the "has_table" pitfall).
    existing = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('news_items')}
    with op.batch_alter_table('news_items') as batch:
        if 'photo_sha' not in existing:
            batch.add_column(sa.Column('photo_sha', sa.String(length=64), nullable=True))
        if 'video_id' not in existing:
            batch.add_column(sa.Column('video_id', sa.Integer(), nullable=True))
            batch.create_foreign_key('fk_news_items_video_id', 'videos', ['video_id'], ['id'])
        if 'document_id' not in existing:
            batch.add_column(sa.Column('document_id', sa.Integer(), nullable=True))
            batch.create_foreign_key('fk_news_items_document_id', 'doc_nodes', ['document_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('news_items') as batch:
        batch.drop_constraint('fk_news_items_document_id', type_='foreignkey')
        batch.drop_constraint('fk_news_items_video_id', type_='foreignkey')
        batch.drop_column('document_id')
        batch.drop_column('video_id')
        batch.drop_column('photo_sha')
