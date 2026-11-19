"""autoimport rules, seen files, linked pieces

Import auto pièces (spec/modules/import-auto-pieces.md §7, Seb 19 November
2026): the imports of an organisation and what each one already looked at;
`nf_pieces` gains `linked`, `drive_id`, `drive_path` for files that stay
in the club's folder. Off by default, switched on for the combat schools.

Revision ID: ebe5ff66e236
Revises: 01173cece550
"""

import sqlalchemy as sa
from alembic import op

revision = "ebe5ff66e236"
down_revision = "01173cece550"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = sa.inspect(bind).get_table_names()
    # deploy.sh runs create_all before Alembic: tables and columns may exist already.
    if "autoimport_rules" not in tables:
        op.create_table(
            "autoimport_rules",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("organization_id", sa.Integer, sa.ForeignKey("ecoles.id"), nullable=False, index=True),
            sa.Column("name", sa.String(30), nullable=False),
            sa.Column("active", sa.Boolean, nullable=False),
            sa.Column("season_id", sa.Integer, nullable=True),
            sa.Column("nature", sa.String(20), nullable=False),
            sa.Column("source_kind", sa.String(20), nullable=False),
            sa.Column("source_ref", sa.Integer, nullable=True),
            sa.Column("source_path", sa.String(1000), nullable=False),
            sa.Column("target_kind", sa.String(20), nullable=False),
            sa.Column("target_ref", sa.Integer, nullable=True),
            sa.Column("target_path", sa.String(1000), nullable=False),
            sa.Column("frequency", sa.String(10), nullable=False),
            sa.Column("at_time", sa.String(5), nullable=False),
            sa.Column("created_status", sa.String(20), nullable=False),
            sa.Column("mail_senders", sa.String(500), nullable=False),
            sa.Column("mail_words", sa.String(500), nullable=False),
            sa.Column("mail_need_amount", sa.Boolean, nullable=False),
            sa.Column("created_by", sa.Integer, nullable=True),
            sa.Column("last_run_at", sa.DateTime, nullable=True),
            sa.Column("last_message", sa.String(300), nullable=False),
        )
    if "autoimport_seen" not in tables:
        op.create_table(
            "autoimport_seen",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("rule_id", sa.Integer, sa.ForeignKey("autoimport_rules.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("source_key", sa.String(500), nullable=False),
            sa.Column("sha256", sa.String(64), nullable=True, index=True),
            sa.Column("note_id", sa.Integer, nullable=True),
            sa.Column("seen_at", sa.DateTime, nullable=False),
            sa.UniqueConstraint("rule_id", "source_key", name="uq_autoimport_seen"),
        )
    colonnes = {c["name"] for c in sa.inspect(bind).get_columns("nf_pieces")}
    with op.batch_alter_table("nf_pieces") as batch:
        if "linked" not in colonnes:
            batch.add_column(sa.Column("linked", sa.Boolean, nullable=False, server_default="0"))
        if "drive_id" not in colonnes:
            batch.add_column(sa.Column("drive_id", sa.Integer, nullable=True))
        if "drive_path" not in colonnes:
            batch.add_column(sa.Column("drive_path", sa.String(1000), nullable=True))
    bind.execute(
        sa.text(
            "INSERT INTO org_modules (org_id, module_key, enabled, updated_at) "
            "SELECT id, 'auto_import', :on, CURRENT_TIMESTAMP FROM ecoles WHERE nature = 'combat' "
            "AND id NOT IN (SELECT org_id FROM org_modules WHERE module_key = 'auto_import')"
        ),
        {"on": True},
    )


def downgrade() -> None:
    op.execute("DELETE FROM org_modules WHERE module_key = 'auto_import'")
    with op.batch_alter_table("nf_pieces") as batch:
        batch.drop_column("drive_path")
        batch.drop_column("drive_id")
        batch.drop_column("linked")
    op.drop_table("autoimport_seen")
    op.drop_table("autoimport_rules")
