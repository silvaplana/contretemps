"""Fights : combattant inconnu (pas du club) sur une place

Revision ID: 297c1e2c1855
Revises: d5e7f9a1b3c6
Create Date: 2026-11-17 00:21:18.068246

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '297c1e2c1855'
down_revision: Union[str, Sequence[str], None] = 'd5e7f9a1b3c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Un combattant qui n'est pas du club (Seb, 17/11) : une case sur la
    # place, person_id restant vide. Faux pour les places existantes.
    with op.batch_alter_table("sc_participants") as batch:
        batch.add_column(sa.Column("outsider", sa.Boolean(), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("sc_participants") as batch:
        batch.drop_column("outsider")
