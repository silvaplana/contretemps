"""documents : dossiers et fichiers (onglet Docs)

Voir appbase/spec/modules/documents.md §4 et documents-phase-contretemps.md
étape 2 : tables du module `documents` (futur module d'AppBase), sans clé
étrangère vers les tables de Contretemps.

Revision ID: f8c1d3e5a7b9
Revises: e6a8c0d2f4b5
Create Date: 2026-10-15 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f8c1d3e5a7b9'
down_revision: Union[str, Sequence[str], None] = 'e6a8c0d2f4b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Base.metadata.create_all (app/main.py) a pu créer les tables avant.
    if 'doc_nodes' in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table('doc_nodes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('org_id', sa.Integer(), nullable=False),
    sa.Column('space', sa.String(length=10), nullable=False),
    sa.Column('owner_person_id', sa.Integer(), nullable=True),
    sa.Column('parent_id', sa.Integer(), nullable=True),
    sa.Column('kind', sa.String(length=10), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('name_search', sa.String(length=255), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=True),
    sa.Column('family', sa.String(length=10), nullable=True),
    sa.Column('system_kind', sa.String(length=10), nullable=True),
    sa.Column('period_id', sa.Integer(), nullable=True),
    sa.Column('restricted', sa.Boolean(), nullable=False),
    sa.Column('pinned', sa.Boolean(), nullable=False),
    sa.Column('current_version_id', sa.Integer(), nullable=True),
    sa.Column('size', sa.Integer(), nullable=True),
    sa.Column('mime', sa.String(length=120), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['parent_id'], ['doc_nodes.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_doc_nodes_org_id'), 'doc_nodes', ['org_id'], unique=False)
    op.create_index(op.f('ix_doc_nodes_owner_person_id'), 'doc_nodes', ['owner_person_id'], unique=False)
    op.create_index(op.f('ix_doc_nodes_parent_id'), 'doc_nodes', ['parent_id'], unique=False)
    op.create_table('doc_stored_files',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('org_id', sa.Integer(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('size', sa.Integer(), nullable=False),
    sa.Column('mime', sa.String(length=120), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('org_id', 'sha256', name='uq_doc_stored_org_sha')
    )
    op.create_index(op.f('ix_doc_stored_files_org_id'), 'doc_stored_files', ['org_id'], unique=False)
    op.create_table('doc_acl',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('node_id', sa.Integer(), nullable=False),
    sa.Column('principal_type', sa.String(length=10), nullable=False),
    sa.Column('principal_id', sa.String(length=60), nullable=False),
    sa.Column('level', sa.String(length=10), nullable=False),
    sa.ForeignKeyConstraint(['node_id'], ['doc_nodes.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('node_id', 'principal_type', 'principal_id', name='uq_doc_acl_principal')
    )
    op.create_index(op.f('ix_doc_acl_node_id'), 'doc_acl', ['node_id'], unique=False)
    op.create_table('doc_activity',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('org_id', sa.Integer(), nullable=False),
    sa.Column('node_id', sa.Integer(), nullable=False),
    sa.Column('person_id', sa.Integer(), nullable=True),
    sa.Column('action', sa.String(length=30), nullable=False),
    sa.Column('detail', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['node_id'], ['doc_nodes.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_doc_activity_node_id'), 'doc_activity', ['node_id'], unique=False)
    op.create_index(op.f('ix_doc_activity_org_id'), 'doc_activity', ['org_id'], unique=False)
    op.create_table('doc_versions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('node_id', sa.Integer(), nullable=False),
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('stored_file_id', sa.Integer(), nullable=False),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['node_id'], ['doc_nodes.id'], ),
    sa.ForeignKeyConstraint(['stored_file_id'], ['doc_stored_files.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_doc_versions_node_id'), 'doc_versions', ['node_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_doc_versions_node_id'), table_name='doc_versions')
    op.drop_table('doc_versions')
    op.drop_index(op.f('ix_doc_activity_org_id'), table_name='doc_activity')
    op.drop_index(op.f('ix_doc_activity_node_id'), table_name='doc_activity')
    op.drop_table('doc_activity')
    op.drop_index(op.f('ix_doc_acl_node_id'), table_name='doc_acl')
    op.drop_table('doc_acl')
    op.drop_index(op.f('ix_doc_stored_files_org_id'), table_name='doc_stored_files')
    op.drop_table('doc_stored_files')
    op.drop_index(op.f('ix_doc_nodes_parent_id'), table_name='doc_nodes')
    op.drop_index(op.f('ix_doc_nodes_owner_person_id'), table_name='doc_nodes')
    op.drop_index(op.f('ix_doc_nodes_org_id'), table_name='doc_nodes')
    op.drop_table('doc_nodes')
