"""HelloAsso and FFST off by default; on in combat schools

Seb, 18 November 2026: HelloAsso and FFST are not on by default. A school
without a row in `org_modules` for them now reads « off » (registry,
`Module.enabled_by_default`). Every existing school keeps its current state
through an explicit row: HelloAsso stays on where it had no row (the old
default); FFST already has a row everywhere (migration d3f5a7c9e1b2), except
schools created since, which keep FFST on. Then combat schools (ASC La
Ciotat, the only one) get both on, as Seb asked.

Revision ID: e4a6c8f0b2d4
Revises: d3f5a7c9e1b2
"""

import sqlalchemy as sa
from alembic import op

revision = "e4a6c8f0b2d4"
down_revision = "d3f5a7c9e1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    for key in ("helloasso", "ffst"):
        bind.execute(
            sa.text(
                "INSERT INTO org_modules (org_id, module_key, enabled, updated_at) "
                "SELECT id, :key, :on, CURRENT_TIMESTAMP FROM ecoles "
                "WHERE id NOT IN (SELECT org_id FROM org_modules WHERE module_key = :key)"
            ),
            {"key": key, "on": True},
        )
    bind.execute(
        sa.text(
            "UPDATE org_modules SET enabled = :on, updated_at = CURRENT_TIMESTAMP "
            "WHERE module_key IN ('helloasso', 'ffst') AND org_id IN (SELECT id FROM ecoles WHERE nature = 'combat')"
        ),
        {"on": True},
    )


def downgrade() -> None:
    # Under the old default no row means on: HelloAsso rows that say « on »
    # can go (FFST rows go with migration d3f5a7c9e1b2).
    op.execute("DELETE FROM org_modules WHERE module_key = 'helloasso' AND enabled = 1")
