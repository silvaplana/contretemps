"""documents: proof log of document signing

Table doc_sign_events (spec/modules/signature-documents.md §6): one row per
event of a signature (validated, sent, opened, read, signed…), insert only,
no foreign key so the proof outlives the file. Created only when missing
(create_all runs before `alembic upgrade head` in deploy.sh).

Revision ID: b5d7f9a1c3e6
Revises: a4c6e8f0b2d5
"""

import sqlalchemy as sa
from alembic import op

revision = "b5d7f9a1c3e6"
down_revision = "a4c6e8f0b2d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("doc_sign_events"):
        return
    op.create_table(
        "doc_sign_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("node_id", sa.Integer(), nullable=False),
        sa.Column("send_id", sa.Integer(), nullable=True),
        sa.Column("event", sa.String(length=12), nullable=False),
        sa.Column("at", sa.DateTime(), nullable=False),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=True),
    )
    op.create_index("ix_doc_sign_events_org_id", "doc_sign_events", ["org_id"])
    op.create_index("ix_doc_sign_events_node_id", "doc_sign_events", ["node_id"])


def downgrade() -> None:
    op.drop_table("doc_sign_events")
