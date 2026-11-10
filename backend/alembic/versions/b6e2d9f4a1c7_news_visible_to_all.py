"""news: « Les actus sont visibles par tout le monde » (end of the test)

spec/modules/actualites.md §2 bis: the test is over (Seb, 10 November). The
🔒 group « Voir les actualités » (`news.read`) is replaced by one setting per
organization in Paramètres d'édition des actus. A new boolean on
news_settings, true for the existing rows (everybody sees the news); off,
only those who publish see them. The now unused 🔒 groups and their
memberships are deleted.

Revision ID: b6e2d9f4a1c7
Revises: d2f4a6c8e0b2
Create Date: 2026-11-10 22:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b6e2d9f4a1c7'
down_revision: Union[str, Sequence[str], None] = 'd2f4a6c8e0b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `create_all` may have added it already (see the "has_table" pitfall).
    colonnes = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('news_settings')}
    if 'visible_to_all' not in colonnes:
        with op.batch_alter_table('news_settings') as batch:
            batch.add_column(sa.Column('visible_to_all', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.execute(
        "DELETE FROM group_members WHERE group_id IN (SELECT id FROM groups WHERE key = 'right.news.read')"
    )
    op.execute("DELETE FROM groups WHERE key = 'right.news.read'")


def downgrade() -> None:
    # The deleted 🔒 groups are not brought back: they were only for the test.
    with op.batch_alter_table('news_settings') as batch:
        batch.drop_column('visible_to_all')
