"""groups: teachers

The Professeur role becomes the « Profs » group (spec/core.md §5.1): one
group per school and season, key `teachers`. Each `professeur` row of
`roles_compte` becomes a membership of that group and is deleted. Running it
twice does nothing more: once moved, there is no `professeur` row left.

Revision ID: a3c5e7f9b1d2
Revises: f2b4d6e8a0c3
"""

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "a3c5e7f9b1d2"
down_revision = "f2b4d6e8a0c3"
branch_labels = None
depends_on = None

_GROUPS = sa.Table(
    "groups", sa.MetaData(),
    sa.Column("id", sa.Integer, primary_key=True), sa.Column("org_id", sa.Integer), sa.Column("season_id", sa.Integer),
    sa.Column("parent_id", sa.Integer), sa.Column("key", sa.String), sa.Column("name", sa.String),
    sa.Column("created_at", sa.DateTime),
)


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = bind.execute(
        sa.text(
            "SELECT c.id, c.ecole_id, c.saison_id FROM roles_compte r JOIN comptes c ON c.id = r.compte_id "
            "WHERE r.role = 'professeur' AND c.ecole_id IS NOT NULL ORDER BY c.id"
        )
    ).fetchall()
    groups: dict[tuple[int, int], int] = {}
    for compte_id, org_id, season_id in rows:
        if (org_id, season_id) not in groups:
            existing = bind.execute(
                sa.text("SELECT id FROM groups WHERE org_id = :o AND season_id = :s AND key = 'teachers'"),
                {"o": org_id, "s": season_id},
            ).scalar()
            groups[(org_id, season_id)] = existing or bind.execute(
                _GROUPS.insert().values(org_id=org_id, season_id=season_id, key="teachers", name="Profs", created_at=now)
            ).inserted_primary_key[0]
        group_id = groups[(org_id, season_id)]
        already = bind.execute(
            sa.text("SELECT 1 FROM group_members WHERE group_id = :g AND member_id = :m"), {"g": group_id, "m": compte_id}
        ).scalar()
        if not already:
            bind.execute(
                sa.text("INSERT INTO group_members (group_id, member_id, created_at) VALUES (:g, :m, :t)"),
                {"g": group_id, "m": compte_id, "t": now},
            )
    bind.execute(sa.text("DELETE FROM roles_compte WHERE role = 'professeur'"))


def downgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    teachers = "SELECT id FROM groups WHERE key = 'teachers'"
    for (compte_id,) in bind.execute(
        sa.text(f"SELECT DISTINCT member_id FROM group_members WHERE group_id IN ({teachers})")
    ).fetchall():
        bind.execute(
            sa.text("INSERT INTO roles_compte (compte_id, role, created_at) VALUES (:c, 'professeur', :t)"),
            {"c": compte_id, "t": now},
        )
    bind.execute(sa.text(f"DELETE FROM group_members WHERE group_id IN ({teachers})"))
    bind.execute(sa.text("DELETE FROM groups WHERE key = 'teachers'"))
