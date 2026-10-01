"""acces_emails : dernier échec d'envoi de mail

Demande utilisateur du 2026-10-02 : un mail qui n'a pas pu être envoyé doit
se lire dans la colonne Statut (date et raison).

Revision ID: c5f8d0e2b3a4
Revises: b4e7c9d1a2f3
Create Date: 2026-10-02 01:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5f8d0e2b3a4'
down_revision: Union[str, Sequence[str], None] = 'b4e7c9d1a2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('acces_emails', sa.Column('echec_envoi_le', sa.DateTime(), nullable=True))
    op.add_column('acces_emails', sa.Column('echec_envoi_raison', sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('acces_emails') as batch:
        batch.drop_column('echec_envoi_raison')
        batch.drop_column('echec_envoi_le')
