"""compte sans école (Superuser) : comptes.ecole_id et famille_id optionnels

Voir spec/SPEC.md §2.5. Le Superuser, propriétaire de l'application, est un
compte au-dessus des écoles : il n'a ni école ni famille. Aucune donnée
existante ne change (tous les comptes actuels gardent leurs valeurs).

Revision ID: b787f0a65803
Revises: e08ed3a9ccbe
Create Date: 2026-09-21 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b787f0a65803'
down_revision: Union[str, Sequence[str], None] = 'e08ed3a9ccbe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # batch : SQLite ne sait pas relâcher un NOT NULL en ALTER TABLE simple,
    # Alembic recrée la table (sans effet sur Postgres).
    with op.batch_alter_table('comptes') as batch:
        batch.alter_column('ecole_id', existing_type=sa.Integer(), nullable=True)
        batch.alter_column('famille_id', existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    # Impossible de remettre NOT NULL tant qu'un Superuser existe : on
    # supprime d'abord les comptes sans école (et leurs rôles).
    op.execute(
        "DELETE FROM roles_compte WHERE compte_id IN (SELECT id FROM comptes WHERE ecole_id IS NULL)"
    )
    op.execute("DELETE FROM comptes WHERE ecole_id IS NULL")
    with op.batch_alter_table('comptes') as batch:
        batch.alter_column('ecole_id', existing_type=sa.Integer(), nullable=False)
        batch.alter_column('famille_id', existing_type=sa.Integer(), nullable=False)
