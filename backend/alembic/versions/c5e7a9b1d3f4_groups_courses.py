"""groups: courses

Each course becomes a sub-group of the « Cours » group of its school and
season (spec/core.md §5.1): `cours.group_id` points to it, and each row of
`eleves_cours` becomes a membership of that group. The `eleves_cours` table
is kept as it was, no longer read nor written (the downgrade copies the
memberships back). Running it twice does nothing more: a course that already
has its group is skipped.

Revision ID: c5e7a9b1d3f4
Revises: b4d6f8a0c2e3
"""

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "c5e7a9b1d3f4"
down_revision = "b4d6f8a0c2e3"
branch_labels = None
depends_on = None

_GROUPS = sa.Table(
    "groups", sa.MetaData(),
    sa.Column("id", sa.Integer, primary_key=True), sa.Column("org_id", sa.Integer), sa.Column("season_id", sa.Integer),
    sa.Column("parent_id", sa.Integer), sa.Column("key", sa.String), sa.Column("name", sa.String),
    sa.Column("created_at", sa.DateTime),
)


def _columns(bind, table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    # create_all (deploy.sh) makes the column on a new base, not on an old one.
    if "group_id" not in _columns(bind, "cours"):
        # batch: SQLite cannot add a foreign key with a plain ALTER TABLE.
        with op.batch_alter_table("cours") as batch:
            batch.add_column(sa.Column("group_id", sa.Integer(), nullable=True))
            batch.create_foreign_key("fk_cours_group_id", "groups", ["group_id"], ["id"])
            batch.create_index("ix_cours_group_id", ["group_id"])
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    parents: dict[tuple[int, int], int] = {}
    rows = bind.execute(
        sa.text("SELECT id, ecole_id, saison_id, nom FROM cours WHERE group_id IS NULL ORDER BY id")
    ).fetchall()
    for cours_id, org_id, season_id, name in rows:
        if (org_id, season_id) not in parents:
            existing = bind.execute(
                sa.text("SELECT id FROM groups WHERE org_id = :o AND season_id = :s AND key = 'courses'"),
                {"o": org_id, "s": season_id},
            ).scalar()
            parents[(org_id, season_id)] = existing or bind.execute(
                _GROUPS.insert().values(org_id=org_id, season_id=season_id, key="courses", name="Cours", created_at=now)
            ).inserted_primary_key[0]
        group_id = bind.execute(
            _GROUPS.insert().values(
                org_id=org_id, season_id=season_id, parent_id=parents[(org_id, season_id)], key="course",
                name=(name or "")[:100], created_at=now,
            )
        ).inserted_primary_key[0]
        bind.execute(sa.text("UPDATE cours SET group_id = :g WHERE id = :c"), {"g": group_id, "c": cours_id})
        if sa.inspect(bind).has_table("eleves_cours"):
            bind.execute(
                sa.text(
                    "INSERT INTO group_members (group_id, member_id, created_at) "
                    "SELECT DISTINCT :g, eleve_id, :t FROM eleves_cours WHERE cours_id = :c"
                ),
                {"g": group_id, "c": cours_id, "t": now},
            )


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("eleves_cours"):
        op.create_table(
            "eleves_cours",
            sa.Column("eleve_id", sa.Integer, sa.ForeignKey("comptes.id"), primary_key=True),
            sa.Column("cours_id", sa.Integer, sa.ForeignKey("cours.id"), primary_key=True),
        )
    bind.execute(sa.text("DELETE FROM eleves_cours"))
    bind.execute(
        sa.text(
            "INSERT INTO eleves_cours (eleve_id, cours_id) SELECT DISTINCT m.member_id, c.id "
            "FROM cours c JOIN group_members m ON m.group_id = c.group_id"
        )
    )
    course_groups = "SELECT id FROM groups WHERE key IN ('course', 'courses')"
    bind.execute(sa.text(f"DELETE FROM group_members WHERE group_id IN ({course_groups})"))
    bind.execute(sa.text("UPDATE cours SET group_id = NULL"))
    bind.execute(sa.text("DELETE FROM groups WHERE key = 'course'"))
    bind.execute(sa.text("DELETE FROM groups WHERE key = 'courses'"))
    with op.batch_alter_table("cours") as batch:
        batch.drop_index("ix_cours_group_id")
        batch.drop_constraint("fk_cours_group_id", type_="foreignkey")
        batch.drop_column("group_id")
