"""groups: Financier access right

The Trésorier role becomes the locked group of the « Accès au Financier »
right (spec/core.md §5.3): one group per school and season, key
`right.finances.access`. Each `tresorier` row of `roles_compte` becomes a
membership of that group and is deleted. Running it twice does nothing more:
once moved, there is no `tresorier` row left.

Revision ID: b4d6f8a0c2e3
Revises: a3c5e7f9b1d2
"""

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "b4d6f8a0c2e3"
down_revision = "a3c5e7f9b1d2"
branch_labels = None
depends_on = None

ROLE = "tresorier"
KEY = "right.finances.access"
NAME = "Accès au Financier"

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
            "WHERE r.role = :role AND c.ecole_id IS NOT NULL ORDER BY c.id"
        ),
        {"role": ROLE},
    ).fetchall()
    groups: dict[tuple[int, int], int] = {}
    for compte_id, org_id, season_id in rows:
        if (org_id, season_id) not in groups:
            existing = bind.execute(
                sa.text("SELECT id FROM groups WHERE org_id = :o AND season_id = :s AND key = :k"),
                {"o": org_id, "s": season_id, "k": KEY},
            ).scalar()
            groups[(org_id, season_id)] = existing or bind.execute(
                _GROUPS.insert().values(org_id=org_id, season_id=season_id, key=KEY, name=NAME, created_at=now)
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
    bind.execute(sa.text("DELETE FROM roles_compte WHERE role = :role"), {"role": ROLE})


def downgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    groups = f"SELECT id FROM groups WHERE key = '{KEY}'"
    for (compte_id,) in bind.execute(
        sa.text(f"SELECT DISTINCT member_id FROM group_members WHERE group_id IN ({groups})")
    ).fetchall():
        bind.execute(
            sa.text("INSERT INTO roles_compte (compte_id, role, created_at) VALUES (:c, :r, :t)"),
            {"c": compte_id, "r": ROLE, "t": now},
        )
    bind.execute(sa.text(f"DELETE FROM group_members WHERE group_id IN ({groups})"))
    bind.execute(sa.text("DELETE FROM groups WHERE key = :k"), {"k": KEY})
