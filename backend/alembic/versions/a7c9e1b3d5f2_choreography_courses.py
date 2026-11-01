"""choreography courses

A choreography can be danced by several courses (Seb, 2026-11-01): new
join table `choregraphies_courses`, filled with each choreography's current
course. `choregraphies.cours_id` stays and holds the first course (season
scope, backups).

Revision ID: a7c9e1b3d5f2
Revises: f3b5d7a9c1e4
Create Date: 2026-11-01 08:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7c9e1b3d5f2'
down_revision: Union[str, Sequence[str], None] = 'f3b5d7a9c1e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `create_all` may have created it already (see the "has_table" pitfall).
    if not sa.inspect(op.get_bind()).has_table('choregraphies_courses'):
        op.create_table(
            'choregraphies_courses',
            sa.Column('choregraphie_id', sa.Integer(), sa.ForeignKey('choregraphies.id'), primary_key=True),
            sa.Column('cours_id', sa.Integer(), sa.ForeignKey('cours.id'), primary_key=True),
        )
        op.create_index('ix_choregraphies_courses_cours_id', 'choregraphies_courses', ['cours_id'])
    op.execute(
        "INSERT INTO choregraphies_courses (choregraphie_id, cours_id) "
        "SELECT id, cours_id FROM choregraphies WHERE id NOT IN "
        "(SELECT choregraphie_id FROM choregraphies_courses)"
    )


def downgrade() -> None:
    op.drop_index('ix_choregraphies_courses_cours_id', table_name='choregraphies_courses')
    op.drop_table('choregraphies_courses')
