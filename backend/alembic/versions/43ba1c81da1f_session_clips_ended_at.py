"""session clips ended at

Fights › Montage shows the start and end time of every filmed session (Seb,
13/11/2026). New nullable column `sc_sessions.ended_at`, set when the camera
is stopped; existing sessions keep it empty (their end is still estimated
from the filmed pieces).

Revision ID: 43ba1c81da1f
Revises: 4267c2aae0de
"""

import sqlalchemy as sa
from alembic import op

revision = "43ba1c81da1f"
down_revision = "4267c2aae0de"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # deploy.sh runs create_all before Alembic: the column may already exist.
    if "ended_at" not in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("sc_sessions")}:
        op.add_column("sc_sessions", sa.Column("ended_at", sa.DateTime, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("sc_sessions") as batch:
        batch.drop_column("ended_at")
