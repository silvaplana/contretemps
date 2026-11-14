"""session clips sound filters

Fights settings (shooting and Labo): two optional filters on the shouts heard,
"only loud shouts" and "only sure words", against words the speech model
invents on quiet passages (Seb, 14/11/2026). Two boolean columns, false by
default, on `sc_club_signs` and `sc_lab_settings`.

Revision ID: d5e7f9a1b3c5
Revises: c4d8e2f6a1b3
"""

import sqlalchemy as sa
from alembic import op

revision = "d5e7f9a1b3c5"
down_revision = "c4d8e2f6a1b3"
branch_labels = None
depends_on = None

TABLES = ("sc_club_signs", "sc_lab_settings")
COLUMNS = ("loud_only", "sure_only")


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    # deploy.sh runs create_all before Alembic: the columns may already exist.
    for table in TABLES:
        for column in COLUMNS:
            if column not in _columns(table):
                op.add_column(table, sa.Column(column, sa.Boolean, nullable=False, server_default=sa.false()))


def downgrade() -> None:
    for table in TABLES:
        with op.batch_alter_table(table) as batch:
            for column in COLUMNS:
                batch.drop_column(column)
