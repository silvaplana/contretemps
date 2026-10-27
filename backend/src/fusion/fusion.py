"""Fusionner deux fiches de la même personne (spec/core.md §4, décision de
Seb du 2026-10-18 : une personne = une fiche).

On garde une fiche ; l'autre lui apporte ses rôles, ses emails, sa fiche
élève, ses cours, ses présences, ses messages, ses notes de frais et ses
fichiers, puis disparaît. Colle propre à Contretemps : elle connaît les
tables de tous les modules, que le core, lui, ne connaît pas.
"""

from __future__ import annotations

from sqlalchemy import Table, and_, select
from sqlalchemy.orm import Session

from comptes import Compte, Comptes, roles
from comptes.models import RoleCompte
from db import Base
from documents_contretemps.adapter import personne_id


class RefusFusion(Exception):
    pass


# Tables où une ligne par (clé, personne) au plus : (table, colonne
# personne, colonne clé). La ligne de la fiche gardée l'emporte.
LIENS_PAR_COMPTE = (
    ("eleves_cours", "eleve_id", "cours_id"),
    ("cours_professeurs", "professeur_id", "cours_id"),
    ("choregraphies_eleves", "eleve_id", "choregraphie_id"),
    ("presences_eleves", "eleve_id", "seance_id"),
    ("presences_profs", "professeur_id", "seance_id"),
    ("message_deliveries", "destinataire_id", "message_id"),
    ("contacts_eleves", "eleve_id", "id"),
    ("group_members", "member_id", "group_id"),
)
COLONNES_PAR_COMPTE = (
    ("videos", "uploaded_by"),
    ("messages", "expediteur_id"),
    ("push_subscriptions", "compte_id"),
)
# Notes de frais et documents désignent la personne par l'id de sa
# première fiche, le même toutes saisons (documents_contretemps.personne_id).
LIENS_PAR_PERSONNE = (
    ("nf_ribs", "person_id", "org_id"),
)
COLONNES_PAR_PERSONNE = (
    ("nf_notes", "person_id"),
    ("nf_notes", "traitee_par"),
    ("nf_notes", "remboursee_par"),
    ("nf_depenses", "person_id"),
    ("doc_nodes", "owner_person_id"),
    ("doc_nodes", "created_by"),
    ("doc_nodes", "updated_by"),
    ("doc_nodes", "deleted_by"),
    ("doc_versions", "created_by"),
    ("doc_activity", "person_id"),
    ("doc_app_versions", "created_by"),
    ("doc_responses", "person_id"),
    ("doc_app_templates", "created_by"),
    ("doc_publications", "published_by"),
    ("doc_sends", "person_id"),
    ("doc_sends", "sent_by"),
)


def _table(nom: str) -> Table | None:
    return Base.metadata.tables.get(nom)


def _deplacer_liens(db: Session, table: Table, colonne: str, cle: str, de, vers, filtre=None) -> None:
    """Passe les lignes de `de` à `vers`, sauf celles dont `vers` a déjà
    l'équivalent (même clé), qui sont supprimées."""
    col, col_cle = table.c[colonne], table.c[cle]
    condition = filtre if filtre is not None else True
    deja = set(db.scalars(select(col_cle).where(and_(col == vers, condition))))
    if deja:
        db.execute(table.delete().where(and_(col == de, col_cle.in_(deja), condition)))
    db.execute(table.update().where(and_(col == de, condition)).values({colonne: vers}))


class Fusion:
    def __init__(self, comptes: Comptes) -> None:
        self.comptes = comptes

    def verifier(self, garde: Compte | None, absorbe: Compte | None) -> None:
        if garde is None or absorbe is None:
            raise RefusFusion("Fiche introuvable")
        if garde.id == absorbe.id:
            raise RefusFusion("Choisissez une autre fiche")
        if roles.is_superuser(garde) or roles.is_superuser(absorbe):
            raise RefusFusion("Le Super User ne se fusionne pas")
        if garde.ecole_id != absorbe.ecole_id or garde.saison_id != absorbe.saison_id:
            raise RefusFusion("Les deux fiches doivent être de la même école et de la même saison")

    def fusionner(self, db: Session, garde: Compte, absorbe: Compte) -> Compte:
        self.verifier(garde, absorbe)
        pg, pa = personne_id(db, garde), personne_id(db, absorbe)

        for role in roles.noms_roles(absorbe):
            if not roles.a_le_role(garde, role):
                garde.roles.append(RoleCompte(role=role))
        garde.definir_emails(garde.emails + absorbe.emails)
        garde.telephone = garde.telephone or absorbe.telephone
        if garde.compte_precedent_id is None and absorbe.compte_precedent_id != garde.id:
            garde.compte_precedent_id = absorbe.compte_precedent_id
        db.flush()

        profils = _table("profils_eleves")
        if profils is not None:
            if db.scalar(select(profils.c.compte_id).where(profils.c.compte_id == garde.id)) is None:
                db.execute(profils.update().where(profils.c.compte_id == absorbe.id).values(compte_id=garde.id))
            else:
                db.execute(profils.delete().where(profils.c.compte_id == absorbe.id))

        for nom, colonne, cle in LIENS_PAR_COMPTE:
            if (table := _table(nom)) is not None:
                _deplacer_liens(db, table, colonne, cle, absorbe.id, garde.id)
        for nom, colonne in COLONNES_PAR_COMPTE:
            if (table := _table(nom)) is not None:
                db.execute(table.update().where(table.c[colonne] == absorbe.id).values({colonne: garde.id}))
        if (membres := _table("conversation_membres")) is not None:
            _deplacer_liens(
                db, membres, "membre_id", "conversation_id", absorbe.id, garde.id,
                filtre=membres.c.membre_type == "compte",
            )
        db.execute(
            Base.metadata.tables["comptes"].update()
            .where(Base.metadata.tables["comptes"].c.compte_precedent_id == absorbe.id)
            .values(compte_precedent_id=garde.id)
        )

        if pa != pg:
            for nom, colonne, cle in LIENS_PAR_PERSONNE:
                if (table := _table(nom)) is not None:
                    _deplacer_liens(db, table, colonne, cle, pa, pg)
            for nom, colonne in COLONNES_PAR_PERSONNE:
                if (table := _table(nom)) is not None:
                    db.execute(table.update().where(table.c[colonne] == pa).values({colonne: pg}))
            if (acl := _table("doc_acl")) is not None:
                _deplacer_liens(
                    db, acl, "principal_id", "node_id", str(pa), str(pg),
                    filtre=acl.c.principal_type == "member",
                )

        db.delete(absorbe)
        db.commit()
        self.comptes.recalculer_familles(db, garde.ecole_id)
        db.refresh(garde)
        return garde
