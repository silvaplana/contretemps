"""comptes.compte_precedent_id : lien vers la fiche de la saison précédente

Voir spec/SPEC.md §2.6 : à la création d'une saison, chaque personne
recopiée reçoit une nouvelle fiche. Ce lien permet de basculer
automatiquement vers la nouvelle fiche une personne restée connectée sur
l'ancienne. Vide pour toutes les fiches existantes.

Revision ID: 7c3e9a1f2d56
Revises: 5a1c0e7d9b42
Create Date: 2026-09-23 23:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c3e9a1f2d56'
down_revision: Union[str, Sequence[str], None] = '5a1c0e7d9b42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # batch : SQLite ne sait pas ajouter une clé étrangère en ALTER TABLE
    # simple, Alembic recrée la table (sans effet sur Postgres).
    with op.batch_alter_table('comptes') as batch:
        batch.add_column(sa.Column('compte_precedent_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_comptes_compte_precedent_id', 'comptes', ['compte_precedent_id'], ['id'])
        batch.create_index('ix_comptes_compte_precedent_id', ['compte_precedent_id'])


def downgrade() -> None:
    with op.batch_alter_table('comptes') as batch:
        batch.drop_index('ix_comptes_compte_precedent_id')
        batch.drop_constraint('fk_comptes_compte_precedent_id', type_='foreignkey')
        batch.drop_column('compte_precedent_id')
