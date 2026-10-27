"""season adjustment rules

Step 7c (spec/core.md §9.2): an option can be a rule written in French
(mode "rule"). Three nullable columns on season_adjustments: the rule as
typed, what the assistant understood, and the calculation it wrote (one
checked Python expression, run by the app). Existing rows keep NULL.

Revision ID: e3f5a7b9c1d2
Revises: d2e4f6a8b0c1
"""

import sqlalchemy as sa
from alembic import op

revision = "e3f5a7b9c1d2"
down_revision = "d2e4f6a8b0c1"
branch_labels = None
depends_on = None

COLUMNS = (
    ("rule", sa.Text),
    ("understood", sa.Text),
    ("calculation", lambda: sa.String(500)),
)


def upgrade() -> None:
    # deploy.sh runs create_all before Alembic: the columns may already exist.
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("season_adjustments")}
    with op.batch_alter_table("season_adjustments") as batch:
        for name, kind in COLUMNS:
            if name not in existing:
                batch.add_column(sa.Column(name, kind(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("season_adjustments") as batch:
        for name, _ in reversed(COLUMNS):
            batch.drop_column(name)
