"""groups: board

Core groups (spec/core.md §5): tables `groups` and `group_members`. The
board becomes groups: « Bureau » and its sub-groups, one set per school and
season, filled from `comptes.bureau_functions`, which is no longer read (the
column stays, to be dropped later). The backend's create_all runs before
`alembic upgrade head` in deploy.sh, so the tables may already exist: the
copy runs only when no board group exists yet.

Revision ID: f2b4d6e8a0c3
Revises: e9a1c3d5f7b8
"""

import json
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "f2b4d6e8a0c3"
down_revision = "e9a1c3d5f7b8"
branch_labels = None
depends_on = None

FUNCTIONS = {
    "president": "Président·e",
    "vice_president": "Vice-président·e",
    "secretary": "Secrétaire",
    "treasurer": "Trésorier·e",
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("groups"):
        op.create_table(
            "groups",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("org_id", sa.Integer(), nullable=False),
            sa.Column("season_id", sa.Integer(), nullable=True),
            sa.Column("parent_id", sa.Integer(), nullable=True),
            sa.Column("key", sa.String(length=60), nullable=True),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["org_id"], ["ecoles.id"]),
            sa.ForeignKeyConstraint(["season_id"], ["saisons.id"]),
            sa.ForeignKeyConstraint(["parent_id"], ["groups.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_groups_org_id", "groups", ["org_id"])
        op.create_index("ix_groups_season_id", "groups", ["season_id"])
        op.create_index("ix_groups_parent_id", "groups", ["parent_id"])
        op.create_index("ix_groups_org_season_key", "groups", ["org_id", "season_id", "key"])
    if not inspector.has_table("group_members"):
        op.create_table(
            "group_members",
            sa.Column("group_id", sa.Integer(), nullable=False),
            sa.Column("member_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
            sa.ForeignKeyConstraint(["member_id"], ["comptes.id"]),
            sa.PrimaryKeyConstraint("group_id", "member_id"),
        )
        op.create_index("ix_group_members_member_id", "group_members", ["member_id"])

    if bind.execute(sa.text("SELECT COUNT(*) FROM groups WHERE key = 'board'")).scalar():
        return
    if "bureau_functions" not in {c["name"] for c in inspector.get_columns("comptes")}:
        return
    groups = sa.Table(
        "groups", sa.MetaData(),
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("org_id", sa.Integer), sa.Column("season_id", sa.Integer),
        sa.Column("parent_id", sa.Integer), sa.Column("key", sa.String), sa.Column("name", sa.String),
        sa.Column("created_at", sa.DateTime),
    )
    members = sa.table(
        "group_members",
        sa.column("group_id", sa.Integer), sa.column("member_id", sa.Integer), sa.column("created_at", sa.DateTime),
    )
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    boards: dict[tuple[int, int], dict[str, int]] = {}
    rows = bind.execute(
        sa.text(
            "SELECT id, ecole_id, saison_id, bureau_functions FROM comptes "
            "WHERE ecole_id IS NOT NULL AND saison_id IS NOT NULL ORDER BY id"
        )
    )
    for compte_id, org_id, season_id, raw in rows.fetchall():
        functions = raw if isinstance(raw, list) else json.loads(raw or "[]")
        functions = [f for f in FUNCTIONS if f in set(functions)]
        if not functions:
            continue
        if (org_id, season_id) not in boards:
            parent_id = bind.execute(
                groups.insert().values(org_id=org_id, season_id=season_id, key="board", name="Bureau", created_at=now)
            ).inserted_primary_key[0]
            boards[(org_id, season_id)] = {
                function: bind.execute(
                    groups.insert().values(
                        org_id=org_id, season_id=season_id, parent_id=parent_id,
                        key=f"board.{function}", name=name, created_at=now,
                    )
                ).inserted_primary_key[0]
                for function, name in FUNCTIONS.items()
            }
        for function in functions:
            bind.execute(
                members.insert().values(group_id=boards[(org_id, season_id)][function], member_id=compte_id, created_at=now)
            )


def downgrade() -> None:
    op.drop_table("group_members")
    op.drop_table("groups")
