"""sparring lab

Fights › Labo (spec/modules/video-combats.md §6.5 bis): coaches test the cutting
on videos already filmed (`sc_lab_tests`, each a video of the `videos`
module, the signs found stored as JSON with a small picture of each), and
the club's ticked signs (`sc_club_signs`, one row per organisation, no row
= every sign). New tables: nothing to carry over.

Revision ID: e8c2a4f6b1d3
Revises: d2f4a6b8c0e1
"""

import sqlalchemy as sa
from alembic import op

revision = "e8c2a4f6b1d3"
down_revision = "d2f4a6b8c0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # deploy.sh runs create_all before Alembic: the tables may already exist.
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "sc_lab_tests" not in tables:
        op.create_table(
            "sc_lab_tests",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("org_id", sa.Integer, nullable=False),
            sa.Column("title", sa.String(150), nullable=False, server_default=""),
            sa.Column("video_id", sa.Integer, sa.ForeignKey("videos.id"), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="processing"),
            sa.Column("signs", sa.Text, nullable=True),
            sa.Column("created_by", sa.Integer, nullable=False),
            sa.Column("created_at", sa.DateTime, nullable=True),
        )
        op.create_index("ix_sc_lab_tests_org_id", "sc_lab_tests", ["org_id"])
    if "sc_club_signs" not in tables:
        op.create_table(
            "sc_club_signs",
            sa.Column("org_id", sa.Integer, primary_key=True),
            sa.Column("signs", sa.String(200), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("sc_club_signs")
    op.drop_index("ix_sc_lab_tests_org_id", table_name="sc_lab_tests")
    op.drop_table("sc_lab_tests")
