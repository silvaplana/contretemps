"""Branchement du module `documents` sur Contretemps (voir le plan
documents-phase-contretemps.md §1 règle 2) : le module ne connaît ni les
écoles, ni les comptes, ni les cours, ni les saisons ; c'est ici qu'on lui
dit ce qu'ils sont.

- organisation = école ; membre = compte (profil actif) ;
- personne = premier compte de la chaîne `compte_precedent_id` : les
  comptes sont recopiés à chaque saison, les droits et les auteurs, eux,
  doivent survivre au changement de saison ;
- groupes = ceux qui existent déjà (Seb, 15 octobre) : les rôles (Admins,
  Professeurs, Élèves) et chaque cours de la saison (ses profs et ses
  élèves) ; rien à recréer ni à tenir à jour à la main ;
- période = saison.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from comptes import Compte, rbac, roles
from cours.models import Cours, cours_professeurs, eleves_cours
from db import get_db
from documents.ports import Member, Period, Principal
from documents.service import normalize_search
from saisons import Saison
from saisons.portee import TOUTES_SAISONS, toutes_saisons

DOSSIER_DOCUMENTS = Path(os.environ.get("DOCUMENTS_DIR", "./data/documents"))
# Taille maximale d'un fichier envoyé (Mo).
TAILLE_MAX_MO = int(os.environ.get("DOCUMENTS_TAILLE_MAX_MO", "200"))

_ROLES = {
    roles.ADMIN: ("Admins", "rôle"),
    roles.PROFESSEUR: ("Professeurs", "rôle"),
    roles.ELEVE: ("Élèves", "rôle"),
}


def nom_affiche(compte: Compte) -> str:
    return f"{compte.prenom} {compte.nom}".strip()


def personne_id(db: Session, compte: Compte) -> int:
    """Id du premier compte de la chaîne (le même toutes saisons)."""
    vus = {compte.id}
    while compte.compte_precedent_id is not None:
        precedent = db.get(Compte, compte.compte_precedent_id, execution_options={TOUTES_SAISONS: True})
        if precedent is None or precedent.id in vus:
            break
        vus.add(precedent.id)
        compte = precedent
    return compte.id


def _saison_courante(db: Session, ecole_id: int) -> int | None:
    with toutes_saisons(db):
        return db.scalar(select(Saison.id).where(Saison.ecole_id == ecole_id).order_by(Saison.id.desc()))


def _groupes(db: Session, compte: Compte) -> frozenset[str]:
    noms = {f"role:{r.role}" for r in compte.roles}
    if roles.is_owner(compte):
        noms.add("role:admin")
    cours_prof = db.scalars(select(cours_professeurs.c.cours_id).where(cours_professeurs.c.professeur_id == compte.id))
    cours_eleve = db.scalars(select(eleves_cours.c.cours_id).where(eleves_cours.c.eleve_id == compte.id))
    noms |= {f"course:{i}" for i in list(cours_prof) + list(cours_eleve)}
    return frozenset(noms)


def membre_appelant(db: Session = Depends(get_db), compte: Compte = Depends(rbac.compte_appelant)) -> Member:
    """Dépendance FastAPI : la personne qui appelle, vue par le module."""
    if compte is None:
        raise HTTPException(status_code=401, detail="Session requise")
    superuser = roles.is_superuser(compte)
    admin = roles.is_admin(compte) or roles.is_owner(compte)
    return Member(
        person_id=personne_id(db, compte),
        org_id=compte.ecole_id or 0,
        display_name=nom_affiche(compte),
        is_admin=admin,
        is_superuser=superuser,
        # Pas d'espace Personnel pour les élèves (Seb, 15 octobre).
        has_personal_space=superuser or admin or roles.is_prof(compte),
        groups=_groupes(db, compte),
    )


class AnnuaireContretemps:
    """Port `Directory` : personnes et groupes d'une école."""

    def _personnes(self, db: Session, ids: set[int]) -> dict[int, Compte]:
        if not ids:
            return {}
        with toutes_saisons(db):
            return {c.id: c for c in db.scalars(select(Compte).where(Compte.id.in_(ids)))}

    def person_names(self, db: Session, org_id: int, person_ids: set[int]) -> dict[int, str]:
        return {i: nom_affiche(c) for i, c in self._personnes(db, set(person_ids)).items()}

    def _taille_cours(self, db: Session, cours_id: int) -> int:
        profs = db.scalars(select(cours_professeurs.c.professeur_id).where(cours_professeurs.c.cours_id == cours_id))
        eleves = db.scalars(select(eleves_cours.c.eleve_id).where(eleves_cours.c.cours_id == cours_id))
        return len(set(profs) | set(eleves))

    def describe(self, db: Session, org_id: int, principals: list[tuple[str, str]]) -> dict[tuple[str, str], Principal]:
        resultat: dict[tuple[str, str], Principal] = {}
        ids_personnes = {int(i) for t, i in principals if t == "member" and i.isdigit()}
        personnes = self._personnes(db, ids_personnes)
        for t, i in principals:
            if t == "member" and i.isdigit() and int(i) in personnes:
                resultat[(t, i)] = Principal("member", i, nom_affiche(personnes[int(i)]), "membre")
            elif t == "group" and i.startswith("role:") and i[5:] in _ROLES:
                libelle, detail = _ROLES[i[5:]]
                resultat[(t, i)] = Principal("group", i, libelle, detail)
            elif t == "group" and i.startswith("course:") and i[7:].isdigit():
                with toutes_saisons(db):
                    cours = db.get(Cours, int(i[7:]))
                if cours is not None and cours.ecole_id == org_id:
                    n = self._taille_cours(db, cours.id)
                    resultat[(t, i)] = Principal("group", i, f"Cours {cours.nom}", f"cours · {n} personne{'s' if n > 1 else ''}")
        return resultat

    def search(self, db: Session, org_id: int, query: str, limit: int = 20) -> list[Principal]:
        texte = normalize_search(query)
        groupes = [Principal("group", f"role:{r}", libelle, detail) for r, (libelle, detail) in _ROLES.items()]
        saison = _saison_courante(db, org_id)
        for cours in db.scalars(
            select(Cours).where(Cours.ecole_id == org_id, Cours.saison_id == saison).order_by(Cours.ordre, Cours.id)
        ):
            n = self._taille_cours(db, cours.id)
            groupes.append(Principal("group", f"course:{cours.id}", f"Cours {cours.nom}", f"cours · {n} personne{'s' if n > 1 else ''}"))
        groupes = [g for g in groupes if texte in normalize_search(g.label)]
        personnes: list[Principal] = []
        if texte:
            motif = f"%{query.strip()}%"
            comptes = db.scalars(
                select(Compte)
                .where(
                    Compte.ecole_id == org_id,
                    Compte.saison_id == saison,
                    or_(Compte.nom.ilike(motif), Compte.prenom.ilike(motif)),
                )
                .order_by(Compte.prenom, Compte.nom)
                .limit(limit)
            )
            vus = set()
            for compte in comptes:
                pid = personne_id(db, compte)
                if pid in vus:
                    continue
                vus.add(pid)
                role = roles.role_principal(r.role for r in compte.roles) if compte.roles else "membre"
                detail = {"admin": "admin", "professeur": "professeur", "eleve": "élève"}.get(role, "membre")
                personnes.append(Principal("member", str(pid), nom_affiche(compte), detail))
        return (groupes + personnes)[:limit]


class SaisonsContretemps:
    """Port `Periods` : les saisons de l'école ; la courante est la plus
    récente (voir saisons/saisons.py)."""

    def list(self, db: Session, org_id: int) -> list[Period]:
        with toutes_saisons(db):
            saisons = list(db.scalars(select(Saison).where(Saison.ecole_id == org_id).order_by(Saison.id)))
        courante = saisons[-1].id if saisons else None
        return [Period(id=s.id, name=s.nom, is_current=s.id == courante) for s in saisons]
