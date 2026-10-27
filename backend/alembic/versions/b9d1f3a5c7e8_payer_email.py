"""payer email

Step 5 (spec/core.md §4.4): each record gets a « payer email »; a family is
the records with the same one (empty = the record's first email). Until now
a family was the records linked by any shared email. Each family of several
records gets the email most of its records carry (the parent's), so families
stay exactly the same. Same work as comptes/reprise_payeurs.py.

Revision ID: b9d1f3a5c7e8
Revises: f8b0d2e4a6c7
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.engine import Connection

revision = "b9d1f3a5c7e8"
down_revision = "f8b0d2e4a6c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "payer_email" not in {c["name"] for c in sa.inspect(bind).get_columns("comptes")}:
        op.add_column("comptes", sa.Column("payer_email", sa.String(255), nullable=True))
    reprendre_payeurs(bind)


def downgrade() -> None:
    with op.batch_alter_table("comptes") as batch:
        batch.drop_column("payer_email")


def reprendre_payeurs(connexion: Connection, ecole_id: int | None = None) -> int:
    """Remplit `comptes.payer_email` des familles de plusieurs fiches qui
    n'en ont pas encore. Renvoie le nombre de fiches remplies."""
    filtre = "" if ecole_id is None else " AND c.ecole_id = :ecole"
    lignes = connexion.execute(
        text(
            "SELECT c.famille_id, c.id, e.email FROM comptes c "
            "LEFT JOIN emails_compte e ON e.compte_id = c.id "
            "WHERE c.famille_id IS NOT NULL AND c.payer_email IS NULL" + filtre + " ORDER BY c.id, e.id"
        ),
        {"ecole": ecole_id},
    ).all()
    familles: dict[int, dict[int, list[str]]] = {}
    for famille_id, compte_id, email in lignes:
        emails = familles.setdefault(famille_id, {}).setdefault(compte_id, [])
        if email:
            emails.append(email)
    remplies = 0
    for fiches in familles.values():
        if len(fiches) < 2:
            continue
        compte: dict[str, int] = {}
        for emails in fiches.values():
            for email in emails:
                compte[email] = compte.get(email, 0) + 1
        if not compte:
            continue
        # La plus portée ; à égalité, la première rencontrée (dict ordonné).
        payeur = max(compte, key=compte.get)
        connexion.execute(
            text("UPDATE comptes SET payer_email = :p WHERE id IN (" + ",".join(str(i) for i in fiches) + ")"),
            {"p": payeur},
        )
        remplies += len(fiches)
    return remplies
