"""suppression des codes d'accès et du code de récupération

Voir spec/SPEC.md §2.2, §6.1 et §6.3 : chacun a désormais son mot de passe
(table acces_emails). Disparaissent :
- ecoles.code_acces_admin / code_acces_prof / code_acces_eleve ;
- comptes.code_recuperation (question « animal de compagnie ») ;
- comptes.hashed_password_ou_code (le mot de passe du Superuser a été
  recopié dans acces_emails par la migration précédente).

Revision ID: b4e7c9d1a2f3
Revises: 9d2f4b6a8c10
Create Date: 2026-10-01 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4e7c9d1a2f3'
down_revision: Union[str, Sequence[str], None] = '9d2f4b6a8c10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CODES = ('code_acces_admin', 'code_acces_prof', 'code_acces_eleve')


def upgrade() -> None:
    # batch : SQLite recrée la table pour supprimer des colonnes
    # proprement (sans effet particulier sur Postgres).
    with op.batch_alter_table('ecoles') as batch:
        for colonne in CODES:
            batch.drop_column(colonne)
    with op.batch_alter_table('comptes') as batch:
        batch.drop_column('code_recuperation')
        batch.drop_column('hashed_password_ou_code')


def downgrade() -> None:
    # Les valeurs supprimées ne reviennent pas : codes vides (l'ancienne
    # connexion par code ne fonctionne donc plus tant qu'un admin ne les a
    # pas ressaisis), pas de code de récupération. Le mot de passe du
    # Superuser est recopié depuis acces_emails.
    with op.batch_alter_table('comptes') as batch:
        batch.add_column(sa.Column('hashed_password_ou_code', sa.String(length=255), nullable=True))
        batch.add_column(sa.Column('code_recuperation', sa.String(length=255), nullable=True))
    op.execute(
        "UPDATE comptes SET hashed_password_ou_code = "
        "(SELECT a.mot_de_passe_hache FROM acces_emails a WHERE a.email = LOWER(TRIM(comptes.email))) "
        "WHERE ecole_id IS NULL"
    )
    with op.batch_alter_table('ecoles') as batch:
        for colonne in CODES:
            batch.add_column(sa.Column(colonne, sa.String(length=50), nullable=False, server_default=''))
