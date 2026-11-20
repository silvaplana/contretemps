"""merge heads: auto import licences (e5b7c9d1f3a2) and chart account proposal (b797b4e89b45)

Two migrations were merged into main the same night from d4e8a2c6f1b3;
this joins them (no schema change).

Revision ID: 014cfb3cc4d7
Revises: e5b7c9d1f3a2, b797b4e89b45
"""

revision = "014cfb3cc4d7"
down_revision = ("e5b7c9d1f3a2", "b797b4e89b45")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
