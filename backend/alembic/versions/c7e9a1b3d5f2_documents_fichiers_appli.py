"""Documents : fichiers de l'appli (versions JSON, réponses, modèles de l'école, pages en ligne, envois)

Revision ID: c7e9a1b3d5f2
Revises: f8c1d3e5a7b9
Create Date: 2026-10-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c7e9a1b3d5f2'
down_revision: Union[str, Sequence[str], None] = 'f8c1d3e5a7b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Base.metadata.create_all (app/main.py) a pu créer les tables avant.
    tables = sa.inspect(op.get_bind()).get_table_names()
    if 'doc_app_versions' not in tables:
        op.create_table(
            'doc_app_versions',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('node_id', sa.Integer(), sa.ForeignKey('doc_nodes.id'), nullable=False),
            sa.Column('number', sa.Integer(), nullable=False),
            sa.Column('content', sa.JSON(), nullable=False),
            sa.Column('origin', sa.String(length=10), nullable=False),
            sa.Column('created_by', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.UniqueConstraint('node_id', 'number', name='uq_doc_app_version_number'),
        )
        op.create_index('ix_doc_app_versions_node_id', 'doc_app_versions', ['node_id'])
    if 'doc_responses' not in tables:
        op.create_table(
            'doc_responses',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('org_id', sa.Integer(), nullable=False),
            sa.Column('node_id', sa.Integer(), sa.ForeignKey('doc_nodes.id'), nullable=False),
            sa.Column('version_id', sa.Integer(), sa.ForeignKey('doc_app_versions.id'), nullable=False),
            sa.Column('person_id', sa.Integer(), nullable=True),
            sa.Column('email', sa.String(length=255), nullable=True),
            sa.Column('status', sa.String(length=10), nullable=False),
            sa.Column('is_test', sa.Boolean(), nullable=False),
            sa.Column('source', sa.String(length=10), nullable=False),
            sa.Column('values', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_doc_responses_org_id', 'doc_responses', ['org_id'])
        op.create_index('ix_doc_responses_node_id', 'doc_responses', ['node_id'])
    if 'doc_app_templates' not in tables:
        op.create_table(
            'doc_app_templates',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('org_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('family', sa.String(length=10), nullable=False),
            sa.Column('content', sa.JSON(), nullable=False),
            sa.Column('source_node_id', sa.Integer(), nullable=True),
            sa.Column('hidden', sa.Boolean(), nullable=False),
            sa.Column('created_by', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_doc_app_templates_org_id', 'doc_app_templates', ['org_id'])
    if 'doc_publications' not in tables:
        op.create_table(
            'doc_publications',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('org_id', sa.Integer(), nullable=False),
            sa.Column('node_id', sa.Integer(), nullable=False),
            sa.Column('slug', sa.String(length=40), nullable=False),
            sa.Column('version_id', sa.Integer(), nullable=True),
            sa.Column('published_by', sa.Integer(), nullable=True),
            sa.Column('published_at', sa.DateTime(), nullable=True),
            sa.Column('unpublished_at', sa.DateTime(), nullable=True),
            sa.Column('visits', sa.Integer(), nullable=False),
            sa.UniqueConstraint('org_id', 'slug', name='uq_doc_publication_slug'),
        )
        op.create_index('ix_doc_publications_org_id', 'doc_publications', ['org_id'])
        op.create_index('ix_doc_publications_node_id', 'doc_publications', ['node_id'])
    if 'doc_sends' not in tables:
        op.create_table(
            'doc_sends',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('org_id', sa.Integer(), nullable=False),
            sa.Column('node_id', sa.Integer(), nullable=False),
            sa.Column('token', sa.String(length=64), nullable=False, unique=True),
            sa.Column('person_id', sa.Integer(), nullable=True),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('email', sa.String(length=255), nullable=True),
            sa.Column('channel', sa.String(length=10), nullable=False),
            sa.Column('test', sa.Boolean(), nullable=False),
            sa.Column('status', sa.String(length=10), nullable=False),
            sa.Column('error', sa.String(length=255), nullable=True),
            sa.Column('sent_by', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('sent_at', sa.DateTime(), nullable=True),
            sa.Column('opened_at', sa.DateTime(), nullable=True),
            sa.Column('answered_at', sa.DateTime(), nullable=True),
            sa.Column('response_id', sa.Integer(), nullable=True),
        )
        op.create_index('ix_doc_sends_org_id', 'doc_sends', ['org_id'])
        op.create_index('ix_doc_sends_node_id', 'doc_sends', ['node_id'])


def downgrade() -> None:
    op.drop_table('doc_sends')
    op.drop_table('doc_publications')
    op.drop_table('doc_app_templates')
    op.drop_table('doc_responses')
    op.drop_table('doc_app_versions')
