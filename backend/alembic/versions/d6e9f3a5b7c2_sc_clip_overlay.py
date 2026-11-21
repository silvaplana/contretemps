"""sc clip overlay

Fights, extended Timer (Seb, 21/11/2026): what to draw on an archived fight
(names, chrono, winner, music). A JSON column on the clip, emptied once the
video is redone (session_clips/overlay.py): a pending job belongs to its
clip, no need for a table of its own.

Revision ID: d6e9f3a5b7c2
Revises: c5d8e2f4a6b1
"""

import sqlalchemy as sa
from alembic import op

revision = "d6e9f3a5b7c2"
down_revision = "c5d8e2f4a6b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # deploy.sh runs create_all before Alembic: the column may already exist.
    if "overlay" not in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("sc_clips")}:
        with op.batch_alter_table("sc_clips") as batch:
            batch.add_column(sa.Column("overlay", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("sc_clips") as batch:
        batch.drop_column("overlay")
