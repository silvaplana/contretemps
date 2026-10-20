"""documents: attendance sheet of an assembly

Table doc_attendance (spec/modules/procurations.md §4 and §5, step 2): one
row per person marked present at a general assembly. Created only when
missing (create_all runs before `alembic upgrade head` in deploy.sh).

Revision ID: e3f5a7b9c1d4
Revises: d2e4f6a8b0c3
"""

import sqlalchemy as sa
from alembic import op

revision = "e3f5a7b9c1d4"
down_revision = "d2e4f6a8b0c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("doc_attendance"):
        op.create_table(
            "doc_attendance",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("org_id", sa.Integer(), nullable=False),
            sa.Column("node_id", sa.Integer(), nullable=False),
            sa.Column("person_id", sa.Integer(), nullable=False),
            sa.Column("present_at", sa.DateTime(), nullable=True),
            sa.Column("marked_by", sa.Integer(), nullable=True),
            sa.Column("source", sa.String(length=10), nullable=False),
            sa.UniqueConstraint("node_id", "person_id", name="uq_doc_attendance_person"),
        )
        op.create_index("ix_doc_attendance_org_id", "doc_attendance", ["org_id"])
        op.create_index("ix_doc_attendance_node_id", "doc_attendance", ["node_id"])


def downgrade() -> None:
    op.drop_table("doc_attendance")
