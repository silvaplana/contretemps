"""Fights : combats déjà ouverts par chaque personne (pastille)

Revision ID: e36ccfe307ce
Revises: 297c1e2c1855
Create Date: 2026-11-17 00:50:09.123102

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e36ccfe307ce'
down_revision: Union[str, Sequence[str], None] = '297c1e2c1855'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Les combats qu'une personne a déjà ouverts (pastille de Fights, Seb
    # 17/11). Une ligne par (personne, combat) : la pastille compte les
    # combats validés de la personne sans ligne. Les combats déjà validés
    # aujourd'hui comptent comme vus, pour ne pas allumer une pastille de
    # tous les anciens combats.
    # `create_all` may have added it already (see the "has_table" pitfall).
    if not sa.inspect(op.get_bind()).has_table("sc_viewed"):
        op.create_table(
            "sc_viewed",
            sa.Column("person_id", sa.Integer(), nullable=False),
            sa.Column("clip_id", sa.Integer(), sa.ForeignKey("sc_clips.id"), nullable=False),
            sa.PrimaryKeyConstraint("person_id", "clip_id"),
        )
        op.create_index("ix_sc_viewed_clip_id", "sc_viewed", ["clip_id"])
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM sc_viewed")).scalar():
        return
    op.execute(
        "INSERT INTO sc_viewed (person_id, clip_id) "
        "SELECT DISTINCT p.person_id, p.clip_id FROM sc_participants p "
        "JOIN sc_clips c ON c.id = p.clip_id "
        "WHERE p.person_id IS NOT NULL AND NOT c.to_check"
    )


def downgrade() -> None:
    op.drop_index("ix_sc_viewed_clip_id", table_name="sc_viewed")
    op.drop_table("sc_viewed")
