"""session clips sound thresholds

Fights settings: the thresholds of the two shout filters (#300), set with a
slider (Seb, 14/11/2026): `loud_db` (dB above the background noise, 6 by
default) and `sure_min` (Whisper word score, 0.5 by default), on
`sc_club_signs` and `sc_lab_settings`.

Revision ID: e6f8a0b2c4d6
Revises: d5e7f9a1b3c5
"""

import sqlalchemy as sa
from alembic import op

revision = "e6f8a0b2c4d6"
down_revision = "d5e7f9a1b3c5"
branch_labels = None
depends_on = None

TABLES = ("sc_club_signs", "sc_lab_settings")
COLUMNS = (("loud_db", "6.0"), ("sure_min", "0.5"))


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    # deploy.sh runs create_all before Alembic: the columns may already exist.
    for table in TABLES:
        for column, default in COLUMNS:
            if column not in _columns(table):
                op.add_column(table, sa.Column(column, sa.Float, nullable=False, server_default=sa.text(default)))


def downgrade() -> None:
    for table in TABLES:
        with op.batch_alter_table(table) as batch:
            for column, _ in COLUMNS:
                batch.drop_column(column)
