"""consommations_ia : relevé du coût des opérations d'IA

Voir spec/SPEC.md §5.1.1, section « Usage ressources et IA de la saison »
(demande du 2026-10-15).

Revision ID: a2c4e6f8b0d1
Revises: f1a2b3c4d5e6
Create Date: 2026-10-15 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a2c4e6f8b0d1'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # La table peut déjà exister : l'appli crée les tables manquantes à son
    # démarrage.
    if 'consommations_ia' in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        'consommations_ia',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('ecole_id', sa.Integer(), sa.ForeignKey('ecoles.id'), nullable=False),
        sa.Column('saison_id', sa.Integer(), sa.ForeignKey('saisons.id'), nullable=False),
        sa.Column('categorie', sa.String(length=50), nullable=False),
        sa.Column('cout_usd', sa.Float(), nullable=False),
        sa.Column('detail', sa.String(length=200), nullable=True),
        sa.Column('cree_le', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_consommations_ia_ecole_id', 'consommations_ia', ['ecole_id'])
    op.create_index('ix_consommations_ia_saison_id', 'consommations_ia', ['saison_id'])


def downgrade() -> None:
    op.drop_table('consommations_ia')
