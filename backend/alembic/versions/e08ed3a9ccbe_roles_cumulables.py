"""roles cumulables : table roles_compte, suppression de comptes.role

Voir spec/SPEC.md §2.1 et §6.3bis. Un compte peut désormais avoir plusieurs
rôles (ex. professeur ET admin) : ils passent du champ `comptes.role` à une
table de liaison `roles_compte` (une ligne par rôle détenu).

Conversion des données existantes :
- chaque compte garde son rôle actuel, recopié dans `roles_compte` ;
- le plus ancien admin de chaque école (plus petit id) reçoit en plus le
  rôle `owner` (§2.4 : le premier admin d'une école en est l'Owner).

Revision ID: e08ed3a9ccbe
Revises: 11a534a5cb6f
Create Date: 2026-09-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e08ed3a9ccbe'
down_revision: Union[str, Sequence[str], None] = '11a534a5cb6f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # La table peut déjà exister, VIDE : au démarrage, app/main.py fait un
    # `create_all` qui crée les tables manquantes — si le nouveau code a
    # démarré avant que cette migration passe, `roles_compte` est là mais
    # sans aucune ligne. On ne la recrée pas, on la remplit.
    inspecteur = sa.inspect(op.get_bind())
    if 'roles_compte' not in inspecteur.get_table_names():
        op.create_table(
            'roles_compte',
            sa.Column('compte_id', sa.Integer(), sa.ForeignKey('comptes.id'), nullable=False),
            sa.Column('role', sa.String(length=20), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('compte_id', 'role'),
        )
        op.create_index('ix_roles_compte_compte_id', 'roles_compte', ['compte_id'])
    else:
        op.execute("DELETE FROM roles_compte")

    op.execute(
        "INSERT INTO roles_compte (compte_id, role, created_at) "
        "SELECT id, role, created_at FROM comptes"
    )
    op.execute(
        "INSERT INTO roles_compte (compte_id, role, created_at) "
        "SELECT MIN(id), 'owner', CURRENT_TIMESTAMP FROM comptes "
        "WHERE role = 'admin' GROUP BY ecole_id"
    )

    # batch : SQLite ne sait pas supprimer une colonne ni un index lié en
    # ALTER TABLE simple, Alembic recrée la table (sans effet sur Postgres).
    with op.batch_alter_table('comptes') as batch:
        batch.drop_index('ix_compte_ecole_role')
        batch.drop_column('role')


def downgrade() -> None:
    with op.batch_alter_table('comptes') as batch:
        batch.add_column(sa.Column('role', sa.String(length=20), nullable=True))
    # Un seul rôle possible dans l'ancien modèle : on garde le plus élevé
    # (admin > professeur > eleve ; owner n'était pas un rôle et disparaît).
    for role in ('eleve', 'professeur', 'admin'):
        op.execute(
            "UPDATE comptes SET role = '" + role + "' WHERE id IN "
            "(SELECT compte_id FROM roles_compte WHERE role = '" + role + "')"
        )
    with op.batch_alter_table('comptes') as batch:
        batch.alter_column('role', existing_type=sa.String(length=20), nullable=False)
        batch.create_index('ix_compte_ecole_role', ['ecole_id', 'role'])
    op.drop_index('ix_roles_compte_compte_id', table_name='roles_compte')
    op.drop_table('roles_compte')
