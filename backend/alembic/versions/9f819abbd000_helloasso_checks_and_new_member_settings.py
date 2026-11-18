"""helloasso checks and new member settings

Spec/modules/helloasso.md §7.5: the check of each member's files
(`helloasso_checks`, filed under the HelloAsso id of the membership), and
two settings of the school's connection, off by default: check the files of
a new member, notify the admins of a new member.

Revision ID: 9f819abbd000
Revises: a7c9e1b3d5f8
Create Date: 2026-11-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9f819abbd000'
down_revision: Union[str, Sequence[str], None] = 'a7c9e1b3d5f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `create_all` at start-up may have made the table, never the columns of
    # an existing table: each one is tested.
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('helloasso_checks'):
        _create_checks()
    columns = {c['name'] for c in inspector.get_columns('org_helloasso')}
    with op.batch_alter_table('org_helloasso') as batch_op:
        if 'check_files' not in columns:
            batch_op.add_column(sa.Column('check_files', sa.Boolean(), nullable=False, server_default='0'))
        if 'notify_new' not in columns:
            batch_op.add_column(sa.Column('notify_new', sa.Boolean(), nullable=False, server_default='0'))


def _create_checks() -> None:
    op.create_table(
        'helloasso_checks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('item_id', sa.String(length=40), nullable=False),
        sa.Column('first_name', sa.String(length=255), nullable=False),
        sa.Column('last_name', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('issues', sa.JSON(), nullable=False),
        sa.Column('manual', sa.Boolean(), nullable=False),
        sa.Column('model', sa.String(length=60), nullable=True),
        sa.Column('cost', sa.Float(), nullable=False),
        sa.Column('checked_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['ecoles.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('org_id', 'item_id'),
    )
    op.create_index(op.f('ix_helloasso_checks_org_id'), 'helloasso_checks', ['org_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('org_helloasso') as batch_op:
        batch_op.drop_column('notify_new')
        batch_op.drop_column('check_files')
    op.drop_index(op.f('ix_helloasso_checks_org_id'), table_name='helloasso_checks')
    op.drop_table('helloasso_checks')
