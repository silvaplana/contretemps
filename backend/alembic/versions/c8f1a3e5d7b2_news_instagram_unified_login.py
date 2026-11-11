"""news: Instagram through Meta's Unified Login, hashtag filter, drafts

spec/modules/actualites.md §6 bis (Seb, 11 November 2026). New Meta apps no
longer offer Instagram Login: « Se connecter avec Instagram » goes through
Unified Login, whose key never expires and whose account is read by its id on
graph.facebook.com. Two columns on news_instagram: `ig_user_id` (null for a
pasted key) and `refreshes` (true for the existing rows: a pasted key is
renewed every week). Two settings on news_settings: `instagram_hashtag`, only
the posts with this hashtag come in ('' = all, the existing behaviour), and
`instagram_publish` (true: published at once, as before; false: drafts).

Revision ID: c8f1a3e5d7b2
Revises: e4a6c8d0f2b9
Create Date: 2026-11-11 22:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8f1a3e5d7b2'
down_revision: Union[str, Sequence[str], None] = 'e4a6c8d0f2b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table: str) -> set[str]:
    return {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    # `create_all` may have added them already (see the "has_table" pitfall).
    instagram = _columns('news_instagram')
    with op.batch_alter_table('news_instagram') as batch:
        if 'ig_user_id' not in instagram:
            batch.add_column(sa.Column('ig_user_id', sa.String(length=40), nullable=True))
        if 'refreshes' not in instagram:
            batch.add_column(sa.Column('refreshes', sa.Boolean(), nullable=False, server_default=sa.true()))
    settings = _columns('news_settings')
    with op.batch_alter_table('news_settings') as batch:
        if 'instagram_hashtag' not in settings:
            batch.add_column(sa.Column('instagram_hashtag', sa.String(length=100), nullable=False, server_default=''))
        if 'instagram_publish' not in settings:
            batch.add_column(sa.Column('instagram_publish', sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    with op.batch_alter_table('news_settings') as batch:
        batch.drop_column('instagram_publish')
        batch.drop_column('instagram_hashtag')
    with op.batch_alter_table('news_instagram') as batch:
        batch.drop_column('refreshes')
        batch.drop_column('ig_user_id')
