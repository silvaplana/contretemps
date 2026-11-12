"""sparring club framing

Club settings of the cutting, tuned in Fights > Labo (spec/modules/
video-combats.md §5, Seb 12/11/2026): the framing of the clips (`wide`,
`medium`, `tight`) and the seconds skipped at the start and at the end of
each fight. New columns with defaults on `sc_club_signs`: existing rows
keep the wide shot and whole gestures, as before.

Revision ID: f1c3e5a7b9d4
Revises: e8c2a4f6b1d3
"""

import sqlalchemy as sa
from alembic import op

revision = "f1c3e5a7b9d4"
down_revision = "e8c2a4f6b1d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # deploy.sh runs create_all before Alembic: the columns may already exist.
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("sc_club_signs")}
    if "framing" not in columns:
        op.add_column("sc_club_signs", sa.Column("framing", sa.String(10), nullable=False, server_default="wide"))
    if "start_skip" not in columns:
        op.add_column("sc_club_signs", sa.Column("start_skip", sa.Float, nullable=False, server_default="0"))
    if "end_skip" not in columns:
        op.add_column("sc_club_signs", sa.Column("end_skip", sa.Float, nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("sc_club_signs") as batch:
        batch.drop_column("end_skip")
        batch.drop_column("start_skip")
        batch.drop_column("framing")
