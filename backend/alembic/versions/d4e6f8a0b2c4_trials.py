"""trials: module Essai (spec/modules/essai.md §7)

Revision ID: d4e6f8a0b2c4
Revises: e4a6c8b0d2f3
Create Date: 2026-11-18 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e6f8a0b2c4"
down_revision: str | None = "e4a6c8b0d2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    # `create_all` au démarrage a pu créer les tables avant la migration.
    if not sa.inspect(bind).has_table("trial_terms"):
        op.create_table(
            "trial_terms",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("org_id", sa.Integer(), nullable=False),
            sa.Column("number", sa.Integer(), nullable=False),
            sa.Column("waiver", sa.Text(), nullable=False),
            sa.Column("parental_consent", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["org_id"], ["ecoles.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_trial_terms_org_id", "trial_terms", ["org_id"])
        op.create_table(
            "trial_settings",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("org_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("subtitle", sa.String(length=300), nullable=False),
            sa.Column("intro", sa.Text(), nullable=False),
            sa.Column("rules", sa.JSON(), nullable=False),
            sa.Column("min_age", sa.Integer(), nullable=False),
            sa.Column("schedule", sa.JSON(), nullable=False),
            sa.Column("places", sa.JSON(), nullable=False),
            sa.Column("contacts", sa.JSON(), nullable=False),
            sa.Column("certificate_hint", sa.String(length=300), nullable=False),
            sa.Column("terms_id", sa.Integer(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["org_id"], ["ecoles.id"]),
            sa.ForeignKeyConstraint(["terms_id"], ["trial_terms.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("org_id"),
        )
        op.create_table(
            "trial_students",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("org_id", sa.Integer(), nullable=False),
            sa.Column("first_name", sa.String(length=100), nullable=False),
            sa.Column("last_name", sa.String(length=100), nullable=False),
            sa.Column("age", sa.Integer(), nullable=True),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("phone", sa.String(length=40), nullable=True),
            sa.Column("parent_name", sa.String(length=200), nullable=True),
            sa.Column("comment", sa.Text(), nullable=False),
            sa.Column("family", sa.String(length=32), nullable=False),
            sa.Column("token", sa.String(length=64), nullable=False),
            sa.Column("terms_id", sa.Integer(), nullable=False),
            sa.Column("waiver_accepted", sa.Boolean(), nullable=False),
            sa.Column("certificate_at", sa.DateTime(), nullable=True),
            sa.Column("ip", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("course1_date", sa.Date(), nullable=True),
            sa.Column("course1_mode", sa.String(length=10), nullable=True),
            sa.Column("course2_date", sa.Date(), nullable=True),
            sa.Column("course2_mode", sa.String(length=10), nullable=True),
            sa.ForeignKeyConstraint(["org_id"], ["ecoles.id"]),
            sa.ForeignKeyConstraint(["terms_id"], ["trial_terms.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token"),
        )
        op.create_index("ix_trial_students_org_id", "trial_students", ["org_id"])
        op.create_index("ix_trial_students_family", "trial_students", ["family"])
        op.create_table(
            "trial_signatures",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("org_id", sa.Integer(), nullable=False),
            sa.Column("family", sa.String(length=32), nullable=False),
            sa.Column("signer_name", sa.String(length=200), nullable=False),
            sa.Column("children", sa.JSON(), nullable=False),
            sa.Column("png", sa.LargeBinary(), nullable=False),
            sa.Column("terms_id", sa.Integer(), nullable=False),
            sa.Column("ip", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["org_id"], ["ecoles.id"]),
            sa.ForeignKeyConstraint(["terms_id"], ["trial_terms.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_trial_signatures_org_id", "trial_signatures", ["org_id"])
        op.create_index("ix_trial_signatures_family", "trial_signatures", ["family"])
    # Pas de ligne dans org_modules : le module est éteint partout
    # (`Module.enabled_by_default=False`), chaque école l'allume elle-même.

def downgrade() -> None:
    op.execute("DELETE FROM org_modules WHERE module_key = 'trials'")
    op.drop_table("trial_signatures")
    op.drop_table("trial_students")
    op.drop_table("trial_settings")
    op.drop_table("trial_terms")
