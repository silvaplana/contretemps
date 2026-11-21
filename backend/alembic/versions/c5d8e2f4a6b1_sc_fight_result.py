"""sc fight result

Fights, extended Timer (Seb, 21/11/2026): the result of a filmed fight.
The winner is a flag on the participant, like `outsider` (a fight has no
ordered sides, so the winner is a property of one of its two people); a
draw belongs to nobody, so it is a flag on the clip.

Revision ID: c5d8e2f4a6b1
Revises: b4e7a1c93d26
"""

import sqlalchemy as sa
from alembic import op

revision = "c5d8e2f4a6b1"
down_revision = "b4e7a1c93d26"
branch_labels = None
depends_on = None

COLUMNS = (("sc_participants", "winner"), ("sc_clips", "draw"))


def upgrade() -> None:
    # deploy.sh runs create_all before Alembic: the columns may already exist.
    for table, column in COLUMNS:
        if column not in {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}:
            with op.batch_alter_table(table) as batch:
                batch.add_column(sa.Column(column, sa.Boolean(), nullable=False, server_default="0"))


def downgrade() -> None:
    for table, column in COLUMNS:
        with op.batch_alter_table(table) as batch:
            batch.drop_column(column)
