"""access orgs: the schools that know an address

Each school only sees the access status of the addresses it knows (spec/
core.md §6.4, Seb 12/11/2026): it invited them, or the person opened one of
its profiles. A school that adds someone already invited by another school
shows "Inviter", not that other school's progress. New table `access_orgs`.
Filled from the past: an address invited or activated at a time when a card
of that school already had it is known by that school.

Revision ID: 7a2e02d6f0aa
Revises: f1c3e5a7b9d4
"""

import sqlalchemy as sa
from alembic import op

revision = "7a2e02d6f0aa"
down_revision = "f1c3e5a7b9d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # deploy.sh runs create_all before Alembic: the table may already exist (empty).
    if not sa.inspect(op.get_bind()).has_table("access_orgs"):
        op.create_table(
            "access_orgs",
            sa.Column("access_email_id", sa.Integer, sa.ForeignKey("acces_emails.id"), primary_key=True),
            sa.Column("org_id", sa.Integer, sa.ForeignKey("ecoles.id"), primary_key=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
        )
    op.execute(
        """
        INSERT INTO access_orgs (access_email_id, org_id, created_at)
        SELECT DISTINCT a.id, c.ecole_id, CURRENT_TIMESTAMP
        FROM acces_emails a
        JOIN emails_compte e ON e.email = a.email
        JOIN comptes c ON c.id = e.compte_id
        WHERE c.ecole_id IS NOT NULL
          AND ((a.invite_le IS NOT NULL AND e.created_at <= a.invite_le)
               OR (a.profil_finalise_le IS NOT NULL AND e.created_at <= a.profil_finalise_le))
          AND NOT EXISTS (
            SELECT 1 FROM access_orgs o WHERE o.access_email_id = a.id AND o.org_id = c.ecole_id
          )
        """
    )


def downgrade() -> None:
    op.drop_table("access_orgs")
