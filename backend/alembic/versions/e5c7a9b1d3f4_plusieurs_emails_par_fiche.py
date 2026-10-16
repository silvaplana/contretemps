"""Plusieurs emails par fiche : table emails_compte (spec §2.1, §6.3)

Revision ID: e5c7a9b1d3f4
Revises: d4b6f8a0c2e1
Create Date: 2026-10-16

Chaque `comptes.email` non vide devient une ligne de `emails_compte` (en
minuscules ; une cellule qui contenait déjà plusieurs adresses séparées
par « ; » ou « , » en donne plusieurs). La colonne `comptes.email` reste
en base, plus lue ni écrite par l'appli : un retour en arrière reste
possible sans perte. La table peut déjà exister, vide (créée au démarrage
par Base.metadata.create_all, voir app/main.py) : elle est alors gardée.
"""
import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e5c7a9b1d3f4'
down_revision: Union[str, Sequence[str], None] = 'd4b6f8a0c2e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspection = sa.inspect(bind)
    if 'emails_compte' not in inspection.get_table_names():
        op.create_table(
            'emails_compte',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('compte_id', sa.Integer(), sa.ForeignKey('comptes.id'), nullable=False),
            sa.Column('email', sa.String(255), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.UniqueConstraint('compte_id', 'email', name='uq_email_compte'),
        )
        op.create_index('ix_emails_compte_compte_id', 'emails_compte', ['compte_id'])
        op.create_index('ix_emails_compte_email', 'emails_compte', ['email'])
    if 'email' not in {c['name'] for c in inspection.get_columns('comptes')}:
        return
    deja = {(c, e) for c, e in bind.execute(sa.text('SELECT compte_id, email FROM emails_compte'))}
    lignes = []
    for compte_id, brut, cree_le in bind.execute(
        sa.text("SELECT id, email, created_at FROM comptes WHERE email IS NOT NULL AND email <> ''")
    ):
        for email in dict.fromkeys(e.strip().lower() for e in re.split(r'[;,\s]+', brut) if e.strip()):
            if (compte_id, email) not in deja:
                lignes.append({'compte_id': compte_id, 'email': email, 'created_at': cree_le})
    if lignes:
        bind.execute(
            sa.text('INSERT INTO emails_compte (compte_id, email, created_at) VALUES (:compte_id, :email, :created_at)'),
            lignes,
        )


def downgrade() -> None:
    # La colonne comptes.email a été gardée telle quelle : les emails
    # ajoutés depuis (2e adresse d'une fiche) sont perdus au retour.
    op.drop_index('ix_emails_compte_email', 'emails_compte')
    op.drop_index('ix_emails_compte_compte_id', 'emails_compte')
    op.drop_table('emails_compte')
