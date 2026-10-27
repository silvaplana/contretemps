"""session clips

Tables of the Sparring module (spec/modules/video-combats.md §6.7): filmed
sessions, their clips, who is in each clip, who attended. Skipped when
`create_all` (deploy.sh) already made the tables. The module is switched
off in every existing school (one `org_modules` row each): it is built for
a fighting club first.

Revision ID: ee886b89a201
Revises: e7a9c1d3f5b6
"""

import sqlalchemy as sa
from alembic import op

revision = "ee886b89a201"
down_revision = "e7a9c1d3f5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("sc_sessions"):
        op.create_table(
            "sc_sessions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("org_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=150), nullable=False),
            sa.Column("held_on", sa.Date(), nullable=False),
            sa.Column("raw_video_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("created_by", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["raw_video_id"], ["videos.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_sc_sessions_org_id", "sc_sessions", ["org_id"])
        op.create_table(
            "sc_clips",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("session_id", sa.Integer(), nullable=False),
            sa.Column("video_id", sa.Integer(), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("to_check", sa.Boolean(), nullable=False),
            sa.Column("check_reason", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["session_id"], ["sc_sessions.id"]),
            sa.ForeignKeyConstraint(["video_id"], ["videos.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("video_id"),
        )
        op.create_index("ix_sc_clips_session_id", "sc_clips", ["session_id"])
        op.create_table(
            "sc_participants",
            sa.Column("clip_id", sa.Integer(), nullable=False),
            sa.Column("slot", sa.Integer(), nullable=False),
            sa.Column("person_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["clip_id"], ["sc_clips.id"]),
            sa.PrimaryKeyConstraint("clip_id", "slot"),
        )
        op.create_index("ix_sc_participants_person_id", "sc_participants", ["person_id"])
        op.create_table(
            "sc_attendees",
            sa.Column("session_id", sa.Integer(), nullable=False),
            sa.Column("person_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["session_id"], ["sc_sessions.id"]),
            sa.PrimaryKeyConstraint("session_id", "person_id"),
        )
    # Éteint dans les écoles existantes, sauf si un choix existe déjà.
    bind.execute(
        sa.text(
            "INSERT INTO org_modules (org_id, module_key, enabled, updated_at) "
            "SELECT id, 'session_clips', :off, CURRENT_TIMESTAMP FROM ecoles "
            "WHERE id NOT IN (SELECT org_id FROM org_modules WHERE module_key = 'session_clips')"
        ),
        {"off": False},
    )


def downgrade() -> None:
    op.execute("DELETE FROM org_modules WHERE module_key = 'session_clips'")
    op.drop_table("sc_attendees")
    op.drop_table("sc_participants")
    op.drop_table("sc_clips")
    op.drop_table("sc_sessions")
