"""member known fields

Step 4c (spec/core.md §4.3): the students' fields that were columns of
`profils_eleves` (birth date, address, allergies, medical treatment,
important information) become fields of each season's member sheet, marked
with a hidden `key` so the app still finds them. Their answers are copied to
`member_values`; the old columns stay in the table but are no longer read.
The Admin columns « naissance », « adresse » and « santé » become the
matching field columns (the red cells too).

Revision ID: f8b0d2e4a6c7
Revises: ee886b89a201
"""

import datetime as dt
import json

import sqlalchemy as sa
from alembic import op

revision = "f8b0d2e4a6c7"
down_revision = "ee886b89a201"
branch_labels = None
depends_on = None

# Same as members.fields.KNOWN, with the old column of `profils_eleves`.
KNOWN = [
    ("birth_date", "Date de naissance", "date", "date_naissance"),
    ("address", "Adresse", "long_text", "adresse"),
    ("allergies", "Allergies", "long_text", "allergies"),
    ("medical_treatment", "Traitement médical", "long_text", "traitement_medical"),
    ("important_info", "Informations importantes", "long_text", "informations_importantes"),
]
# Old Admin column → keys of the fields that replace it.
COLUMNS = {
    "naissance": ["birth_date"],
    "adresse": ["address"],
    "sante": ["allergies", "medical_treatment", "important_info"],
}


def _now():
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def upgrade() -> None:
    bind = op.get_bind()
    if "key" not in {c["name"] for c in sa.inspect(bind).get_columns("member_fields")}:
        op.add_column("member_fields", sa.Column("key", sa.String(30), nullable=True))

    fields = sa.Table(
        "member_fields", sa.MetaData(),
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("org_id", sa.Integer),
        sa.Column("season_id", sa.Integer), sa.Column("label", sa.String), sa.Column("required", sa.Boolean),
        sa.Column("format", sa.String), sa.Column("multiple", sa.Boolean), sa.Column("position", sa.Integer),
        sa.Column("member_sees", sa.Boolean), sa.Column("member_edits", sa.Boolean),
        sa.Column("others_see", sa.Boolean), sa.Column("key", sa.String), sa.Column("created_at", sa.DateTime),
    )
    values = sa.table(
        "member_values",
        sa.column("member_id", sa.Integer), sa.column("field_id", sa.Integer),
        sa.column("value", sa.JSON), sa.column("updated_at", sa.DateTime),
    )

    for season_id, org_id in bind.execute(sa.text("SELECT id, ecole_id FROM saisons")).all():
        ids = dict(
            bind.execute(
                sa.text("SELECT key, id FROM member_fields WHERE season_id = :s AND key IS NOT NULL"), {"s": season_id}
            ).all()
        )
        for position, (key, label, fmt, _) in enumerate(KNOWN, start=-len(KNOWN)):
            if key not in ids:
                ids[key] = bind.execute(
                    fields.insert().values(
                        org_id=org_id, season_id=season_id, label=label, required=False, format=fmt,
                        multiple=False, position=position, member_sees=False, member_edits=False,
                        others_see=False, key=key, created_at=_now(),
                    )
                ).inserted_primary_key[0]

        # Answers: one per student of the season and non-empty column.
        profiles = bind.execute(
            sa.text(
                "SELECT p.compte_id, p.date_naissance, p.adresse, p.allergies, p.traitement_medical, "
                "p.informations_importantes, p.cellules_rouges FROM profils_eleves p "
                "JOIN comptes c ON c.id = p.compte_id WHERE c.saison_id = :s"
            ),
            {"s": season_id},
        ).all()
        for profile in profiles:
            member_id, *answers, red = profile
            for (key, _, _, _), answer in zip(KNOWN, answers):
                if isinstance(answer, str):
                    answer = answer.strip()
                if answer in (None, ""):
                    continue
                if isinstance(answer, dt.date):
                    answer = answer.isoformat()
                exists = bind.execute(
                    sa.text("SELECT 1 FROM member_values WHERE member_id = :m AND field_id = :f"),
                    {"m": member_id, "f": ids[key]},
                ).first()
                if exists is None:
                    bind.execute(values.insert().values(member_id=member_id, field_id=ids[key], value=answer, updated_at=_now()))
            # Red cells (long press in Admin > Élèves) follow their column.
            if red:
                cells = json.loads(red) if isinstance(red, str) else red
                renamed = []
                for cell in cells:
                    for new in [f"field:{ids[k]}" for k in COLUMNS.get(cell, [])] or [cell]:
                        if new not in renamed:
                            renamed.append(new)
                if renamed != cells:
                    bind.execute(
                        sa.text("UPDATE profils_eleves SET cellules_rouges = :r WHERE compte_id = :m"),
                        {"r": json.dumps(renamed), "m": member_id},
                    )

        # Display in Admin: the old columns become the field columns, same place.
        rows = bind.execute(
            sa.text("SELECT key, shown FROM member_columns WHERE season_id = :s ORDER BY position, key"), {"s": season_id}
        ).all()
        if not any(key in COLUMNS for key, _ in rows):
            continue
        renamed = []
        for key, shown in rows:
            for new in [f"field:{ids[k]}" for k in COLUMNS.get(key, [])] or [key]:
                if new not in {k for k, _ in renamed}:
                    renamed.append((new, shown))
        bind.execute(sa.text("DELETE FROM member_columns WHERE season_id = :s"), {"s": season_id})
        for position, (key, shown) in enumerate(renamed):
            bind.execute(
                sa.text(
                    "INSERT INTO member_columns (org_id, season_id, key, shown, position) VALUES (:o, :s, :k, :v, :p)"
                ),
                {"o": org_id, "s": season_id, "k": key, "v": shown, "p": position},
            )


def downgrade() -> None:
    bind = op.get_bind()
    back = {"birth_date": "naissance", "address": "adresse", "allergies": "sante"}
    for field_id, key in bind.execute(sa.text("SELECT id, key FROM member_fields WHERE key IS NOT NULL")).all():
        if key in back:
            bind.execute(
                sa.text("UPDATE member_columns SET key = :old WHERE key = :new"),
                {"old": back[key], "new": f"field:{field_id}"},
            )
        bind.execute(sa.text("DELETE FROM member_columns WHERE key = :new"), {"new": f"field:{field_id}"})
        bind.execute(sa.text("DELETE FROM member_values WHERE field_id = :f"), {"f": field_id})
        bind.execute(sa.text("DELETE FROM member_fields WHERE id = :f"), {"f": field_id})
    with op.batch_alter_table("member_fields") as batch:
        batch.drop_column("key")
