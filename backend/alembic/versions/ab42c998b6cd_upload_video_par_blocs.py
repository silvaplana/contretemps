"""upload video par blocs

Revision ID: ab42c998b6cd
Revises: db76cb584f46
Create Date: 2026-09-16 11:44:52.615524

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ab42c998b6cd'
down_revision: Union[str, Sequence[str], None] = 'db76cb584f46'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'videos',
        sa.Column('statut', sa.String(length=20), nullable=False, server_default='complete'),
    )
    op.add_column(
        'videos',
        sa.Column('compresse', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        'televersements_video',
        sa.Column('id', sa.String(length=32), primary_key=True),
        sa.Column('ecole_id', sa.Integer(), sa.ForeignKey('ecoles.id'), nullable=False),
        sa.Column('cours_id', sa.Integer(), sa.ForeignKey('cours.id'), nullable=False),
        sa.Column('extension', sa.String(length=20), nullable=False),
        sa.Column('octets_total', sa.Integer(), nullable=False),
        sa.Column('octets_recus', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('complet', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('video_id', sa.Integer(), sa.ForeignKey('videos.id'), nullable=True),
        sa.Column('cree_le', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('televersements_video')
    op.drop_column('videos', 'compresse')
    op.drop_column('videos', 'statut')
