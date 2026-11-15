"""session clips min hold

Fights settings: how long a gesture must be held, for every gesture
(Seb, 15/11/2026), `min_hold` in seconds, 1.6 by default, on
`sc_club_signs` and `sc_lab_settings`.

Revision ID: a1b3c5d7e9f2
Revises: f7a9b1c3d5e7
"""

import sqlalchemy as sa
from alembic import op

revision = "a1b3c5d7e9f2"
down_revision = "f7a9b1c3d5e7"
branch_labels = None
depends_on = None

TABLES = ("sc_club_signs", "sc_lab_settings")


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    # deploy.sh runs create_all before Alembic: the column may already exist.
    for table in TABLES:
        if "min_hold" not in _columns(table):
            op.add_column(table, sa.Column("min_hold", sa.Float(), nullable=False, server_default="1.6"))


def downgrade() -> None:
    for table in TABLES:
        with op.batch_alter_table(table) as batch:
            batch.drop_column("min_hold")
