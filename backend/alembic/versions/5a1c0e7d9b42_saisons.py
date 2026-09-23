"""saisons : table saisons et rattachement des données existantes

Voir spec/SPEC.md §2.6 et §6.1bis. Chaque école reçoit une saison
"2026-2027" (du 2026-09-01 au 2027-08-31, renommable ensuite), à laquelle
sont rattachées toutes ses données actuelles. `saison_id` est ajouté aux
tables "racines" (familles, comptes, cours, conversations, inscriptions,
mappings_colonnes_import) ; les autres en héritent via leur compte, cours
ou conversation. Obligatoire partout sauf sur `comptes` (Superuser, sans
école ni saison, §2.5).

La correspondance des colonnes de l'import Excel devient unique par saison
(elle pointe vers des cours, propres à une saison) au lieu de par école.

Revision ID: 5a1c0e7d9b42
Revises: b787f0a65803
Create Date: 2026-09-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5a1c0e7d9b42'
down_revision: Union[str, Sequence[str], None] = 'b787f0a65803'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, saison_id obligatoire ?)
TABLES = [
    ('familles', True),
    ('comptes', False),
    ('cours', True),
    ('conversations', True),
    ('inscriptions', True),
    ('mappings_colonnes_import', True),
]


def upgrade() -> None:
    # Le backend crée au démarrage les tables qui manquent (app/main.py :
    # create_all), et démarre avant qu'on lance la migration : `saisons`
    # peut donc déjà exister, vide et identique au modèle.
    if 'saisons' not in sa.inspect(op.get_bind()).get_table_names():
        _creer_table_saisons()

    op.execute(
        "INSERT INTO saisons (ecole_id, nom, date_debut, date_fin, created_at) "
        "SELECT id, '2026-2027', '2026-09-01', '2027-08-31', CURRENT_TIMESTAMP FROM ecoles "
        "WHERE NOT EXISTS (SELECT 1 FROM saisons s WHERE s.ecole_id = ecoles.id)"
    )

    for table, obligatoire in TABLES:
        op.add_column(table, sa.Column('saison_id', sa.Integer(), nullable=True))
        op.execute(
            f"UPDATE {table} SET saison_id = "
            f"(SELECT MAX(s.id) FROM saisons s WHERE s.ecole_id = {table}.ecole_id)"
        )
        # batch : SQLite ne sait ajouter ni NOT NULL ni clé étrangère en
        # ALTER TABLE simple, Alembic recrée la table (sans effet sur Postgres).
        with op.batch_alter_table(table) as batch:
            if obligatoire:
                batch.alter_column('saison_id', existing_type=sa.Integer(), nullable=False)
            batch.create_foreign_key(f'fk_{table}_saison_id', 'saisons', ['saison_id'], ['id'])
            batch.create_index(f'ix_{table}_saison_id', ['saison_id'])
            if table == 'mappings_colonnes_import':
                batch.drop_constraint('uq_mapping_colonne_ecole_entete', type_='unique')
                batch.create_unique_constraint(
                    'uq_mapping_colonne_saison_entete', ['saison_id', 'en_tete_excel']
                )


def _creer_table_saisons() -> None:
    op.create_table(
        'saisons',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ecole_id', sa.Integer(), nullable=False),
        sa.Column('nom', sa.String(length=50), nullable=False),
        sa.Column('date_debut', sa.Date(), nullable=False),
        sa.Column('date_fin', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['ecole_id'], ['ecoles.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ecole_id', 'nom', name='uq_saison_ecole_nom'),
    )
    op.create_index('ix_saisons_ecole_id', 'saisons', ['ecole_id'])


def downgrade() -> None:
    # Retire juste la notion de saison : n'a de sens que tant que chaque
    # école n'a qu'une saison (sinon les données de toutes ses saisons se
    # retrouvent mélangées).
    for table, _ in reversed(TABLES):
        with op.batch_alter_table(table) as batch:
            if table == 'mappings_colonnes_import':
                batch.drop_constraint('uq_mapping_colonne_saison_entete', type_='unique')
                batch.create_unique_constraint(
                    'uq_mapping_colonne_ecole_entete', ['ecole_id', 'en_tete_excel']
                )
            batch.drop_index(f'ix_{table}_saison_id')
            batch.drop_constraint(f'fk_{table}_saison_id', type_='foreignkey')
            batch.drop_column('saison_id')
    op.drop_index('ix_saisons_ecole_id', table_name='saisons')
    op.drop_table('saisons')
