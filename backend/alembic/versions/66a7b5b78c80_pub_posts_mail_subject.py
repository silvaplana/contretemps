"""pub_posts mail_subject

Revision ID: 66a7b5b78c80
Revises: 014cfb3cc4d7
Create Date: 2026-11-20 08:09:51.298167

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision: str = '66a7b5b78c80'
down_revision: Union[str, Sequence[str], None] = '014cfb3cc4d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The « Objet du mail » typed, kept for the send 10 s later (Seb, 20 November).
    with op.batch_alter_table("pub_posts") as batch_op:
        batch_op.add_column(sa.Column("mail_subject", sa.String(length=200), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("pub_posts") as batch_op:
        batch_op.drop_column("mail_subject")
