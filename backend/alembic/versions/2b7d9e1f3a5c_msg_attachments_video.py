"""msg attachments: videos

Length and compression state of a video sent in a message
(spec/modules/messagerie-instantanee.md §4.5). The backend's create_all runs
before `alembic upgrade head` in deploy.sh but never adds a column to an
existing table: only the missing columns are added.

Revision ID: 2b7d9e1f3a5c
Revises: 1f5a36ab475b
"""

import sqlalchemy as sa
from alembic import op

revision = "2b7d9e1f3a5c"
down_revision = "1f5a36ab475b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("msg_attachments")}
    with op.batch_alter_table("msg_attachments") as batch:
        if "duration" not in existing:
            batch.add_column(sa.Column("duration", sa.Integer(), nullable=True))
        if "compressed" not in existing:
            batch.add_column(sa.Column("compressed", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    with op.batch_alter_table("msg_attachments") as batch:
        batch.drop_column("compressed")
        batch.drop_column("duration")
