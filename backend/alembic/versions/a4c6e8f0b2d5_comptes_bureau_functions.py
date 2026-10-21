"""comptes: bureau functions

Colonne comptes.bureau_functions (spec/core.md §6.4) : les fonctions au
bureau de l'association (président, secrétaire…), une liste JSON, vide par
défaut. Ajoutée seulement si absente (create_all passe avant
`alembic upgrade head` dans deploy.sh et crée la colonne sur une base neuve).

Revision ID: a4c6e8f0b2d5
Revises: e3f5a7b9c1d4
"""

import sqlalchemy as sa
from alembic import op

revision = "a4c6e8f0b2d5"
down_revision = "e3f5a7b9c1d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    colonnes = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("comptes")}
    if "bureau_functions" not in colonnes:
        op.add_column("comptes", sa.Column("bureau_functions", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    with op.batch_alter_table("comptes") as batch:
        batch.drop_column("bureau_functions")
