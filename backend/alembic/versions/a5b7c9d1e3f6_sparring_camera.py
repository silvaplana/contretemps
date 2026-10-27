"""sparring camera

Step 3 of Sparring (spec/modules/video-combats.md §4 and §6.7): the room
camera (`sc_recorders`, paired by a code, polled every 5 s), its 2-minute
pieces (`sc_pieces`, each a video of the `videos` module) and, on clips,
the start of the fight in the filmed session (`start_seconds`) so that
cutting piece by piece never cuts the same fight twice. New tables and a
nullable column: nothing to carry over.

Revision ID: a5b7c9d1e3f6
Revises: d5f7b9a1c3e6
"""

import sqlalchemy as sa
from alembic import op

revision = "a5b7c9d1e3f6"
down_revision = "d5f7b9a1c3e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # deploy.sh runs create_all before Alembic: the tables may already exist.
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "sc_recorders" not in tables:
        op.create_table(
            "sc_recorders",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("org_id", sa.Integer, nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=True, unique=True),
            sa.Column("pairing_code", sa.String(8), nullable=True),
            sa.Column("pairing_expires_at", sa.DateTime, nullable=True),
            sa.Column("state", sa.String(20), nullable=False, server_default="ready"),
            sa.Column("battery_percent", sa.Integer, nullable=True),
            sa.Column("free_bytes", sa.BigInteger, nullable=True),
            sa.Column("pending_pieces", sa.Integer, nullable=False, server_default="0"),
            sa.Column("last_seen_at", sa.DateTime, nullable=True),
            sa.Column("last_upload_at", sa.DateTime, nullable=True),
            sa.Column("session_id", sa.Integer, sa.ForeignKey("sc_sessions.id"), nullable=True),
            sa.Column("started_at", sa.DateTime, nullable=True),
            sa.Column("signal", sa.String(10), nullable=False, server_default="beep"),
        )
        op.create_index("ix_sc_recorders_org_id", "sc_recorders", ["org_id"])
    if "sc_pieces" not in tables:
        op.create_table(
            "sc_pieces",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("session_id", sa.Integer, sa.ForeignKey("sc_sessions.id"), nullable=False),
            sa.Column("position", sa.Integer, nullable=False),
            sa.Column("upload_id", sa.String(32), nullable=False),
            sa.Column("video_id", sa.Integer, sa.ForeignKey("videos.id"), nullable=True),
            sa.Column("last", sa.Boolean, nullable=False, server_default=sa.false()),
            sa.Column("duration_seconds", sa.Float, nullable=True),
        )
        op.create_index("ix_sc_pieces_session_id", "sc_pieces", ["session_id"])
    if "start_seconds" not in {c["name"] for c in sa.inspect(bind).get_columns("sc_clips")}:
        op.add_column("sc_clips", sa.Column("start_seconds", sa.Float, nullable=True))


def downgrade() -> None:
    op.drop_column("sc_clips", "start_seconds")
    op.drop_index("ix_sc_pieces_session_id", table_name="sc_pieces")
    op.drop_table("sc_pieces")
    op.drop_index("ix_sc_recorders_org_id", table_name="sc_recorders")
    op.drop_table("sc_recorders")
