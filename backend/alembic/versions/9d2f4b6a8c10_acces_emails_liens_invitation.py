"""connexion par mot de passe : tables acces_emails et liens_invitation_reinit

Voir spec/SPEC.md §2.2 et §6.3ter. `acces_emails` : une ligne par adresse
email, qui porte le mot de passe haché et le suivi de l'invitation.
`liens_invitation_reinit` : liens d'invitation et de réinitialisation, à usage unique.

Le mot de passe du Superuser (jusqu'ici dans comptes.hashed_password_ou_code)
est recopié sur la ligne de son email : il se connecte comme avant. Personne
d'autre n'a encore de mot de passe. Les colonnes devenues inutiles
(codes d'accès, code de récupération) sont supprimées par une migration à
part.

Revision ID: 9d2f4b6a8c10
Revises: 7c3e9a1f2d56
Create Date: 2026-10-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9d2f4b6a8c10'
down_revision: Union[str, Sequence[str], None] = '7c3e9a1f2d56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Le backend crée au démarrage les tables qui manquent (app/main.py :
    # create_all), et peut démarrer avant la migration : elles peuvent déjà
    # exister, vides et identiques au modèle.
    existantes = sa.inspect(op.get_bind()).get_table_names()
    if 'acces_emails' not in existantes:
        op.create_table(
            'acces_emails',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('email', sa.String(length=255), nullable=False),
            sa.Column('mot_de_passe_hache', sa.String(length=255), nullable=True),
            sa.Column('invite_le', sa.DateTime(), nullable=True),
            sa.Column('invitation_consultee_le', sa.DateTime(), nullable=True),
            sa.Column('profil_finalise_le', sa.DateTime(), nullable=True),
            sa.Column('appli_installee_le', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_acces_emails_email', 'acces_emails', ['email'], unique=True)
    if 'liens_invitation_reinit' not in existantes:
        op.create_table(
            'liens_invitation_reinit',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('acces_email_id', sa.Integer(), nullable=False),
            sa.Column('type', sa.String(length=20), nullable=False),
            sa.Column('jeton_hache', sa.String(length=64), nullable=False),
            sa.Column('expire_le', sa.DateTime(), nullable=False),
            sa.Column('utilise_le', sa.DateTime(), nullable=True),
            sa.Column('ecole_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['ecole_id'], ['ecoles.id']),
            sa.ForeignKeyConstraint(['acces_email_id'], ['acces_emails.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_liens_invitation_reinit_acces_email_id', 'liens_invitation_reinit', ['acces_email_id'])
        op.create_index('ix_liens_invitation_reinit_jeton_hache', 'liens_invitation_reinit', ['jeton_hache'], unique=True)

    # Superuser (compte sans école) : son mot de passe suit son email.
    op.execute(
        "INSERT INTO acces_emails (email, mot_de_passe_hache, profil_finalise_le, created_at) "
        "SELECT LOWER(TRIM(c.email)), c.hashed_password_ou_code, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP "
        "FROM comptes c "
        "WHERE c.ecole_id IS NULL AND c.email IS NOT NULL AND c.hashed_password_ou_code IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM acces_emails u WHERE u.email = LOWER(TRIM(c.email)))"
    )


def downgrade() -> None:
    # Le mot de passe du Superuser est resté dans comptes.hashed_password_ou_code.
    op.drop_index('ix_liens_invitation_reinit_jeton_hache', table_name='liens_invitation_reinit')
    op.drop_index('ix_liens_invitation_reinit_acces_email_id', table_name='liens_invitation_reinit')
    op.drop_table('liens_invitation_reinit')
    op.drop_index('ix_acces_emails_email', table_name='acces_emails')
    op.drop_table('acces_emails')
