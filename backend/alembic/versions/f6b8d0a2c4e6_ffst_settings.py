"""ffst: the school's settings for a licence request

Step 2 of spec/modules/ffst.md §10: three columns on `ffst_connections`,
hard-coded for ASC in Sambo Admin. Discipline of a new request (empty:
asked on screen), birth town when the member's town is not found (empty:
the school's town), « Droit à l'image » ticked on a new request.

Revision ID: f6b8d0a2c4e6
Revises: e4a6c8f0b2d4
"""

import sqlalchemy as sa
from alembic import op

revision = "f6b8d0a2c4e6"
down_revision = "e4a6c8f0b2d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # deploy.sh runs create_all before Alembic: check the columns first.
    colonnes = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("ffst_connections")}
    with op.batch_alter_table("ffst_connections") as batch:
        if "discipline" not in colonnes:
            batch.add_column(sa.Column("discipline", sa.String(60), nullable=False, server_default=""))
        if "default_birth_town" not in colonnes:
            batch.add_column(sa.Column("default_birth_town", sa.String(100), nullable=False, server_default=""))
        if "image_rights" not in colonnes:
            batch.add_column(sa.Column("image_rights", sa.Boolean, nullable=False, server_default=sa.true()))


def downgrade() -> None:
    with op.batch_alter_table("ffst_connections") as batch:
        batch.drop_column("image_rights")
        batch.drop_column("default_birth_town")
        batch.drop_column("discipline")
