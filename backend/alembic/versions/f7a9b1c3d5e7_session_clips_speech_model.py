"""session clips speech model

Fights settings: which listening to use for the shouts (Seb, 14/11/2026),
`speech_model` = "base" (fast, the default) or "small" (more accurate,
slower), on `sc_club_signs` and `sc_lab_settings`.

Revision ID: f7a9b1c3d5e7
Revises: e6f8a0b2c4d6
"""

import sqlalchemy as sa
from alembic import op

revision = "f7a9b1c3d5e7"
down_revision = "e6f8a0b2c4d6"
branch_labels = None
depends_on = None

TABLES = ("sc_club_signs", "sc_lab_settings")


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    # deploy.sh runs create_all before Alembic: the column may already exist.
    for table in TABLES:
        if "speech_model" not in _columns(table):
            op.add_column(table, sa.Column("speech_model", sa.String(10), nullable=False, server_default="base"))


def downgrade() -> None:
    for table in TABLES:
        with op.batch_alter_table(table) as batch:
            batch.drop_column("speech_model")
