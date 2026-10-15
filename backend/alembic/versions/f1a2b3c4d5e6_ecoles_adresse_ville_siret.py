"""écoles : adresse, ville, SIRET et IBAN

Voir spec/SPEC.md §6.1 (demande du 2026-10-15) : optionnels ; ils
remplacent, sur la facture et le dossier d'inscription, les valeurs écrites
dans inscriptions/coordonnees_association.py.

Revision ID: f1a2b3c4d5e6
Revises: e7b0f2a4d5c6
Create Date: 2026-10-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e7b0f2a4d5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    colonnes = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('ecoles')}
    if 'adresse' not in colonnes:
        op.add_column('ecoles', sa.Column('adresse', sa.Text(), nullable=True))
    if 'ville' not in colonnes:
        op.add_column('ecoles', sa.Column('ville', sa.String(length=100), nullable=True))
    if 'siret' not in colonnes:
        op.add_column('ecoles', sa.Column('siret', sa.String(length=14), nullable=True))
    if 'iban' not in colonnes:
        op.add_column('ecoles', sa.Column('iban', sa.String(length=34), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('ecoles') as batch:
        batch.drop_column('iban')
        batch.drop_column('siret')
        batch.drop_column('ville')
        batch.drop_column('adresse')
