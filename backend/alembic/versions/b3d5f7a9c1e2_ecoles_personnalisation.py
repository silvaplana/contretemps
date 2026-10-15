"""écoles : personnalisation de l'application et adresse web

Voir spec/SPEC.md §2.7, §5.1.1 et §6.1 (2026-10-15) : logo, nom en image,
slogan, couleurs, police, nom sous l'icône, et l'adresse
https://<sous_domaine>.contretemps.silvaplana.cloud, obligatoire et unique.
L'école Contretemps (Le Beausset) reçoit `le-beausset` ; une autre école,
son nom normalisé (avec un numéro s'il est pris ou réservé).

Revision ID: b3d5f7a9c1e2
Revises: a2c4e6f8b0d1
Create Date: 2026-10-15 17:00:00.000000

"""
import re
import unicodedata
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b3d5f7a9c1e2'
down_revision: Union[str, Sequence[str], None] = 'a2c4e6f8b0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _colonnes():
    return [
        sa.Column('logo', sa.String(length=300), nullable=True),
        sa.Column('logo_original', sa.String(length=300), nullable=True),
        sa.Column('logo_detourage', sa.String(length=20), nullable=True),
        sa.Column('nom_mode', sa.String(length=10), nullable=False, server_default='texte'),
        sa.Column('nom_image', sa.String(length=300), nullable=True),
        sa.Column('nom_image_original', sa.String(length=300), nullable=True),
        sa.Column('nom_image_detourage', sa.String(length=20), nullable=True),
        sa.Column('slogan', sa.String(length=80), nullable=True),
        sa.Column('couleur_fond', sa.String(length=7), nullable=True),
        sa.Column('couleur_texte', sa.String(length=7), nullable=True),
        sa.Column('couleur_accent', sa.String(length=7), nullable=True),
        sa.Column('police', sa.String(length=30), nullable=True),
        sa.Column('sous_domaine', sa.String(length=40), nullable=True),
        sa.Column('nom_appli', sa.String(length=30), nullable=True),
        sa.Column('ancien_sous_domaine', sa.String(length=40), nullable=True),
        sa.Column('ancien_sous_domaine_jusqu_au', sa.Date(), nullable=True),
        sa.Column('personnalisation_version', sa.Integer(), nullable=False, server_default='1'),
    ]


RESERVES = {"www", "api", "admin", "app", "mail", "contretemps"}


def _normaliser(texte: str) -> str:
    sans_accent = unicodedata.normalize("NFKD", texte or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", sans_accent.lower()).strip("-")[:36].strip("-")


def upgrade() -> None:
    connexion = op.get_bind()
    existantes = {c['name'] for c in sa.inspect(connexion).get_columns('ecoles')}
    for colonne in _colonnes():
        if colonne.name not in existantes:
            op.add_column('ecoles', colonne)

    prises = set()
    for ecole_id, nom, code_postal in connexion.execute(
        sa.text("SELECT id, nom, code_postal FROM ecoles WHERE sous_domaine IS NULL ORDER BY id")
    ).all():
        base = _normaliser(nom)
        if base == "contretemps" and code_postal == "83330":
            base = "le-beausset"
        if len(base) < 3 or base in RESERVES:
            base = _normaliser(f"{nom} {code_postal}") or "ecole"
        adresse, numero = base, 2
        while adresse in prises or adresse in RESERVES:
            adresse, numero = f"{base}-{numero}", numero + 1
        prises.add(adresse)
        connexion.execute(sa.text("UPDATE ecoles SET sous_domaine = :a WHERE id = :i"), {"a": adresse, "i": ecole_id})

    with op.batch_alter_table('ecoles') as batch:
        batch.alter_column('sous_domaine', existing_type=sa.String(length=40), nullable=False)
        batch.create_unique_constraint('uq_ecoles_sous_domaine', ['sous_domaine'])
        batch.create_unique_constraint('uq_ecoles_ancien_sous_domaine', ['ancien_sous_domaine'])


def downgrade() -> None:
    with op.batch_alter_table('ecoles') as batch:
        batch.drop_constraint('uq_ecoles_ancien_sous_domaine', type_='unique')
        batch.drop_constraint('uq_ecoles_sous_domaine', type_='unique')
        for colonne in reversed(_colonnes()):
            batch.drop_column(colonne.name)
