"""news: photos and videos on top of each item, or the text (setting)

spec/modules/actualites.md §4.1: one setting per organization in
Paramètres d'édition des actus, « En haut de chaque actu : Texte | Photo,
vidéo ». A new boolean on news_settings, false (text on top) for the
existing rows; no row still means the defaults.

Revision ID: d5f2b8c1e604
Revises: c4e8a1f7b352
Create Date: 2026-11-09 09:15:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5f2b8c1e604'
down_revision: Union[str, Sequence[str], None] = 'c4e8a1f7b352'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `create_all` may have added it already (see the "has_table" pitfall).
    colonnes = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('news_settings')}
    if 'media_first' not in colonnes:
        with op.batch_alter_table('news_settings') as batch:
            batch.add_column(sa.Column('media_first', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table('news_settings') as batch:
        batch.drop_column('media_first')
