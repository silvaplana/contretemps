"""school android app: the Android app setting replaces frontend/android/ecoles.json

Two new columns on `ecoles`: `appli_android` (on or off) and `apk_cle` (the
app's name in the GitHub release, fixed once). ASC La Ciotat, the only school
of ecoles.json, keeps its key "asc-la-ciotat" so the installed apps keep
updating (personnalisation/appli_android.py, Seb 18/11/2026).

Revision ID: b7d2a9c4e1f3
Revises: c1b18c1cfaa9
"""

import sqlalchemy as sa
from alembic import op

revision = "b7d2a9c4e1f3"
down_revision = "c1b18c1cfaa9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    colonnes = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("ecoles")}
    if "appli_android" not in colonnes:
        op.add_column("ecoles", sa.Column("appli_android", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    if "apk_cle" not in colonnes:
        op.add_column("ecoles", sa.Column("apk_cle", sa.String(40), nullable=True))
    ecoles = sa.table("ecoles", sa.column("sous_domaine"), sa.column("appli_android", sa.Boolean), sa.column("apk_cle"))
    op.execute(
        ecoles.update()
        .where(ecoles.c.sous_domaine == "alliance-sambo-combat-la-ciotat", ecoles.c.apk_cle.is_(None))
        .values(appli_android=True, apk_cle="asc-la-ciotat")
    )


def downgrade() -> None:
    with op.batch_alter_table("ecoles") as table:
        table.drop_column("apk_cle")
        table.drop_column("appli_android")
