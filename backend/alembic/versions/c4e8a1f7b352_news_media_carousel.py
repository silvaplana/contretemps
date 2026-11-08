"""news: several photos and videos per item (carousel)

spec/modules/actualites.md §3.3 (Seb, 8 November): an item's photos and
videos move to news_media, one row each, in order. The existing photo or
video of each item is copied there first, then news_items loses its
photo_sha and video_id columns.

Revision ID: c4e8a1f7b352
Revises: b81f2c6d9e47
Create Date: 2026-11-08 19:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4e8a1f7b352'
down_revision: Union[str, Sequence[str], None] = 'b81f2c6d9e47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    # `create_all` may have created it already (see the "has_table" pitfall).
    if not inspector.has_table('news_media'):
        op.create_table(
            'news_media',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('item_id', sa.Integer(), sa.ForeignKey('news_items.id', ondelete='CASCADE'), nullable=False),
            sa.Column('position', sa.Integer(), nullable=False),
            sa.Column('photo_sha', sa.String(length=64), nullable=True),
            sa.Column('video_id', sa.Integer(), sa.ForeignKey('videos.id'), nullable=True),
        )
        op.create_index('ix_news_media_item_id', 'news_media', ['item_id'])
        op.create_index('ix_news_media_video_id', 'news_media', ['video_id'])
    columns = {c['name'] for c in inspector.get_columns('news_items')}
    if 'photo_sha' in columns:
        bind.execute(sa.text(
            "INSERT INTO news_media (item_id, position, photo_sha, video_id) "
            "SELECT id, 0, photo_sha, video_id FROM news_items WHERE photo_sha IS NOT NULL OR video_id IS NOT NULL"
        ))
        foreign_keys = {fk['name'] for fk in inspector.get_foreign_keys('news_items')}
        with op.batch_alter_table('news_items') as batch:
            if 'fk_news_items_video_id' in foreign_keys:
                batch.drop_constraint('fk_news_items_video_id', type_='foreignkey')
            batch.drop_column('video_id')
            batch.drop_column('photo_sha')


def downgrade() -> None:
    with op.batch_alter_table('news_items') as batch:
        batch.add_column(sa.Column('photo_sha', sa.String(length=64), nullable=True))
        batch.add_column(sa.Column('video_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_news_items_video_id', 'videos', ['video_id'], ['id'])
    # Back to one media per item: the first one.
    op.get_bind().execute(sa.text(
        "UPDATE news_items SET "
        "photo_sha = (SELECT photo_sha FROM news_media m WHERE m.item_id = news_items.id ORDER BY position LIMIT 1), "
        "video_id = (SELECT video_id FROM news_media m WHERE m.item_id = news_items.id ORDER BY position LIMIT 1)"
    ))
    op.drop_index('ix_news_media_video_id', 'news_media')
    op.drop_index('ix_news_media_item_id', 'news_media')
    op.drop_table('news_media')
