"""sparring favorites

« ★ Favoris » in Sparring (spec/modules/video-combats.md §6.7): the clips
each person set aside. New table only: nothing to carry over.

Revision ID: e3f5a7b9c1d2
Revises: d2e4f6a8b0c1
"""

import sqlalchemy as sa
from alembic import op

revision = "e3f5a7b9c1d2"
down_revision = "d2e4f6a8b0c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # deploy.sh runs create_all before Alembic: the table may already exist.
    if "sc_favorites" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "sc_favorites",
            sa.Column("person_id", sa.Integer, primary_key=True),
            sa.Column("clip_id", sa.Integer, sa.ForeignKey("sc_clips.id"), primary_key=True),
        )
        op.create_index("ix_sc_favorites_clip_id", "sc_favorites", ["clip_id"])


def downgrade() -> None:
    op.drop_index("ix_sc_favorites_clip_id", table_name="sc_favorites")
    op.drop_table("sc_favorites")
