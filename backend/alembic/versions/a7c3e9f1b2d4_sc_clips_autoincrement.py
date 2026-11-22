"""sc_clips: never reuse a fight number (SQLite AUTOINCREMENT)

Seb, 22/11: SQLite gives a deleted row's id to the next row; a fight filmed
right after deleting another got the old number and stayed hidden on the
phone. With AUTOINCREMENT, SQLite remembers the highest number ever used.
PostgreSQL sequences never reuse anyway (the flag is ignored there).

Revision ID: a7c3e9f1b2d4
Revises: d6e9f3a5b7c2
"""

import sqlalchemy as sa
from alembic import op

revision = "a7c3e9f1b2d4"
down_revision = "d6e9f3a5b7c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "sqlite" or not sa.inspect(op.get_bind()).has_table("sc_clips"):
        return
    with op.batch_alter_table("sc_clips", recreate="always", table_kwargs={"sqlite_autoincrement": True}):
        pass


def downgrade() -> None:
    pass
