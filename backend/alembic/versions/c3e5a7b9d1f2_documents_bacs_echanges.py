"""Documents : bacs « Échanges » (spec/modules/documents.md §4.7 ter).

Quatre colonnes facultatives sur doc_nodes, remplies seulement pour un
élément posé directement dans un bac : sa date de départ à la corbeille,
son destinataire (comme une ligne de doc_acl) et la date où il l'a ouvert.
Les bacs eux-mêmes sont des dossiers système, créés par l'appli.

Revision ID: c3e5a7b9d1f2
Revises: b2d4f6a8c0e1
"""

import sqlalchemy as sa
from alembic import op

revision = "c3e5a7b9d1f2"
down_revision = "b2d4f6a8c0e1"
branch_labels = None
depends_on = None

COLONNES = (
    ("exchange_until", sa.DateTime()),
    ("for_type", sa.String(10)),
    ("for_id", sa.String(60)),
    ("picked_at", sa.DateTime()),
)


def upgrade() -> None:
    existantes = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("doc_nodes")}
    with op.batch_alter_table("doc_nodes") as batch:
        for nom, genre in COLONNES:
            if nom not in existantes:
                batch.add_column(sa.Column(nom, genre, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("doc_nodes") as batch:
        for nom, _ in reversed(COLONNES):
            batch.drop_column(nom)
