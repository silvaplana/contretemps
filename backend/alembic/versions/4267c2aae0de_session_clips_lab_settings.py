"""session clips lab settings

Fights › Labo gets its own cutting settings, apart from the shooting ones
(`sc_club_signs`, Fights › ⋮ › Paramètres de tournage; Seb 12/11/2026: the
Labo is for experimenting). New table `sc_lab_settings`, one row per
organisation, same columns. Each club's current settings are copied into it,
so the Labo keeps what it shows today; no row = the shooting settings.

Revision ID: 4267c2aae0de
Revises: 7a2e02d6f0aa
"""

import sqlalchemy as sa
from alembic import op

revision = "4267c2aae0de"
down_revision = "7a2e02d6f0aa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # deploy.sh runs create_all before Alembic: the table may already exist.
    if "sc_lab_settings" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "sc_lab_settings",
            sa.Column("org_id", sa.Integer, primary_key=True),
            sa.Column("signs", sa.String(200), nullable=False),
            sa.Column("framing", sa.String(10), nullable=False, server_default="wide"),
            sa.Column("start_skip", sa.Float, nullable=False, server_default="0"),
            sa.Column("end_skip", sa.Float, nullable=False, server_default="0"),
        )
    op.execute(
        "INSERT INTO sc_lab_settings (org_id, signs, framing, start_skip, end_skip) "
        "SELECT org_id, signs, framing, start_skip, end_skip FROM sc_club_signs "
        "WHERE org_id NOT IN (SELECT org_id FROM sc_lab_settings)"
    )


def downgrade() -> None:
    op.drop_table("sc_lab_settings")
