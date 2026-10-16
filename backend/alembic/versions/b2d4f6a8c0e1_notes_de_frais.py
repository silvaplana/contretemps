"""Notes de frais (spec/modules/notes-de-frais.md) : tables nf_*, adresses
mail de l'école (contact, trésorerie). Le rôle `tresorier` n'a besoin de
rien : c'est une ligne de roles_compte.

Revision ID: b2d4f6a8c0e1
Revises: a1c3e5f7b9d2

Les tables peuvent déjà exister, vides (créées au démarrage par
Base.metadata.create_all, voir app/main.py) : elles sont alors gardées.
"""

import sqlalchemy as sa
from alembic import op

revision = "b2d4f6a8c0e1"
down_revision = "a1c3e5f7b9d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspection = sa.inspect(op.get_bind())
    colonnes = {c["name"] for c in inspection.get_columns("ecoles")}
    with op.batch_alter_table("ecoles") as batch:
        for nom in ("email_contact", "email_tresorier"):
            if nom not in colonnes:
                batch.add_column(sa.Column(nom, sa.String(255), nullable=True))

    tables = set(inspection.get_table_names())
    if "nf_categories" not in tables:
        op.create_table(
            "nf_categories",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("org_id", sa.Integer(), nullable=False, index=True),
            sa.Column("libelle", sa.String(60), nullable=False),
            sa.Column("ordre", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
    if "nf_notes" not in tables:
        op.create_table(
            "nf_notes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("org_id", sa.Integer(), nullable=False, index=True),
            sa.Column("person_id", sa.Integer(), nullable=False, index=True),
            sa.Column("titre", sa.String(120), nullable=False),
            sa.Column("statut", sa.String(20), nullable=False, index=True),
            sa.Column("don", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("rib_titulaire", sa.String(120), nullable=True),
            sa.Column("rib_iban", sa.String(34), nullable=True),
            sa.Column("rib_bic", sa.String(11), nullable=True),
            sa.Column("motif_refus", sa.Text(), nullable=True),
            sa.Column("envoyee_le", sa.DateTime(), nullable=False),
            sa.Column("traitee_le", sa.DateTime(), nullable=True),
            sa.Column("traitee_par", sa.Integer(), nullable=True),
            sa.Column("remboursee_le", sa.DateTime(), nullable=True),
            sa.Column("remboursee_par", sa.Integer(), nullable=True),
        )
    if "nf_depenses" not in tables:
        op.create_table(
            "nf_depenses",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("org_id", sa.Integer(), nullable=False, index=True),
            sa.Column("person_id", sa.Integer(), nullable=False, index=True),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("montant_centimes", sa.Integer(), nullable=False),
            sa.Column("categorie_id", sa.Integer(), sa.ForeignKey("nf_categories.id"), nullable=True),
            sa.Column("description", sa.String(200), nullable=False, server_default=""),
            sa.Column("lue_par_ia", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("note_id", sa.Integer(), sa.ForeignKey("nf_notes.id"), nullable=True, index=True),
            sa.Column("creee_le", sa.DateTime(), nullable=False),
        )
    if "nf_pieces" not in tables:
        op.create_table(
            "nf_pieces",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("depense_id", sa.Integer(), sa.ForeignKey("nf_depenses.id"), nullable=False, index=True),
            sa.Column("chemin", sa.String(500), nullable=False),
            sa.Column("type_mime", sa.String(100), nullable=False),
            sa.Column("nom", sa.String(200), nullable=False, server_default=""),
            sa.Column("taille", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("ordre", sa.Integer(), nullable=False, server_default="0"),
        )
    if "nf_ribs" not in tables:
        op.create_table(
            "nf_ribs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("org_id", sa.Integer(), nullable=False),
            sa.Column("person_id", sa.Integer(), nullable=False),
            sa.Column("titulaire", sa.String(120), nullable=True),
            sa.Column("iban", sa.String(34), nullable=False),
            sa.Column("bic", sa.String(11), nullable=True),
            sa.Column("modifie_le", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("org_id", "person_id", name="uq_nf_rib_personne"),
        )


def downgrade() -> None:
    for table in ("nf_ribs", "nf_pieces", "nf_depenses", "nf_notes", "nf_categories"):
        op.drop_table(table)
    with op.batch_alter_table("ecoles") as batch:
        batch.drop_column("email_tresorier")
        batch.drop_column("email_contact")
