"""notes de frais: storage place of manual receipts

Emplacement des pièces manuelles (spec/modules/financier.md §8.13): per
school, nature and season, where the file of a receipt entered with « + » goes.
No row = today's folders, so nothing changes until someone sets a place.

Revision ID: d4e8a2c6f1b3
Revises: c7a1e3f5b9d2
"""

import sqlalchemy as sa
from alembic import op

revision = "d4e8a2c6f1b3"
down_revision = "c7a1e3f5b9d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # deploy.sh runs create_all before Alembic: the table may exist already.
    if sa.inspect(op.get_bind()).has_table("nf_storage_places"):
        return
    op.create_table(
        "nf_storage_places",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.Integer, nullable=False, index=True),
        sa.Column("nature", sa.String(20), nullable=False),
        sa.Column("season_id", sa.Integer, nullable=True),
        sa.Column("target_kind", sa.String(10), nullable=False),
        sa.Column("drive_id", sa.Integer, nullable=True),
        sa.Column("path", sa.String(1000), nullable=False),
        sa.Column("by_month", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("org_id", "nature", "season_id", name="uq_nf_storage_place"),
    )


def downgrade() -> None:
    op.drop_table("nf_storage_places")
