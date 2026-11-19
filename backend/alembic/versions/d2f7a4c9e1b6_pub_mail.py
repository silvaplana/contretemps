"""pub mail: a post sent by mail to the members (Seb, 19 November 2026)

Revision ID: d2f7a4c9e1b6
Revises: 59291952bcf2
Create Date: 2026-11-19 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2f7a4c9e1b6'
down_revision: Union[str, Sequence[str], None] = '59291952bcf2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `create_all` may have added them already (see the "has_table" pitfall).
    inspecteur = sa.inspect(op.get_bind())
    colonnes = {c['name'] for c in inspecteur.get_columns('pub_posts')}
    with op.batch_alter_table('pub_posts') as batch:
        if 'mail_requested_at' not in colonnes:
            batch.add_column(sa.Column('mail_requested_at', sa.DateTime(), nullable=True))
        if 'mail_sent_at' not in colonnes:
            batch.add_column(sa.Column('mail_sent_at', sa.DateTime(), nullable=True))
        if 'mailed_to' not in colonnes:
            batch.add_column(sa.Column('mailed_to', sa.Integer(), nullable=True))
    if not inspecteur.has_table('pub_mail_optouts'):
        op.create_table(
            'pub_mail_optouts',
            sa.Column('org_id', sa.Integer(), sa.ForeignKey('ecoles.id'), primary_key=True),
            sa.Column('email', sa.String(length=255), primary_key=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
        )


def downgrade() -> None:
    op.drop_table('pub_mail_optouts')
    with op.batch_alter_table('pub_posts') as batch:
        batch.drop_column('mailed_to')
        batch.drop_column('mail_sent_at')
        batch.drop_column('mail_requested_at')
