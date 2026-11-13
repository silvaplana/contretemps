"""session clips timeline

Fights › Montage: an opened session shows the timeline of the signs found,
like a Labo test (Seb, 13/11/2026). New nullable column `sc_sessions.signs`
(JSON, filled by the cutting), and `sc_club_signs.show_timeline` (shooting
settings, true by default).

Revision ID: 49d79f526eb1
Revises: 43ba1c81da1f
"""

import sqlalchemy as sa
from alembic import op

revision = "49d79f526eb1"
down_revision = "43ba1c81da1f"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    # deploy.sh runs create_all before Alembic: the columns may already exist.
    if "signs" not in _columns("sc_sessions"):
        op.add_column("sc_sessions", sa.Column("signs", sa.Text, nullable=True))
    if "show_timeline" not in _columns("sc_club_signs"):
        op.add_column("sc_club_signs", sa.Column("show_timeline", sa.Boolean, nullable=False, server_default=sa.true()))


def downgrade() -> None:
    with op.batch_alter_table("sc_club_signs") as batch:
        batch.drop_column("show_timeline")
    with op.batch_alter_table("sc_sessions") as batch:
        batch.drop_column("signs")
