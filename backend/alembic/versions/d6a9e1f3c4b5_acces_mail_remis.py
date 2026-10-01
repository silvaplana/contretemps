"""acces_emails : dernier mail remis (signalé par Brevo)

Revision ID: d6a9e1f3c4b5
Revises: c5f8d0e2b3a4
Create Date: 2026-10-02 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6a9e1f3c4b5'
down_revision: Union[str, Sequence[str], None] = 'c5f8d0e2b3a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('acces_emails', sa.Column('mail_remis_le', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('acces_emails') as batch:
        batch.drop_column('mail_remis_le')
