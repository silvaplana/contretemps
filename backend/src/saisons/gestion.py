"""Créer une saison (avec duplication) et éditer la saison courante (voir
spec/SPEC.md §2.6 et §5.1.1).

Séparé de saisons.py : ce module s'appuie sur les comptes, cours et élèves,
qui dépendent eux-mêmes de saisons.py (import circulaire sinon). Il n'est
importé que par le receiver.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from comptes import roles as r
from comptes.models import Compte, Famille, RoleCompte
from cours.models import Cours, CoursHoraireSupplementaire, cours_professeurs, eleves_cours
from eleves.models import ContactEleve, ProfilEleve
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Saison
from .portee import toutes_saisons
from .saisons import saison_courante_id

# Ordre d'attribution des rôles recopiés (owner exige admin, voir §6.3bis).
_ORDRE_ROLES = [r.ELEVE, r.PROFESSEUR, r.ADMIN, r.OWNER]


class ErreurSaison(ValueError):
    """Demande refusée : message lisible, renvoyé tel quel à l'écran (409)."""


@dataclass
class Duplication:
    """Cases cochées à la création (§2.6) : profs → cours → élèves, chacune
    exigeant la précédente. Les admins sont toujours recopiés."""

    profs: bool = False
    cours: bool = False
    eleves: bool = False


class GestionSaisons:
    def lister(self, db: Session, ecole_id: int) -> list[Saison]:
        """De la plus récente (la courante) à la plus ancienne."""
        return list(db.scalars(select(Saison).where(Saison.ecole_id == ecole_id).order_by(Saison.id.desc())))

    def modifier_courante(self, db: Session, ecole_id: int, nom: str, date_debut: dt.date, date_fin: dt.date) -> Saison:
        """Nom et dates seulement ; les anciennes saisons ne se modifient pas."""
        saison = db.get(Saison, saison_courante_id(db, ecole_id))
        nom = self._valider(db, ecole_id, nom, date_debut, date_fin, sauf_id=saison.id)
        saison.nom, saison.date_debut, saison.date_fin = nom, date_debut, date_fin
        db.commit()
        db.refresh(saison)
        return saison

    def creer(
        self,
        db: Session,
        ecole_id: int,
        nom: str,
        date_debut: dt.date,
        date_fin: dt.date,
        duplication: Duplication,
    ) -> tuple[Saison, dict[int, int]]:
        """Crée la saison, qui devient aussitôt la courante (la précédente
        passe en lecture seule), et y recopie ce qui est demandé. Renvoie
        aussi la correspondance ancienne fiche → nouvelle fiche, pour que
        l'admin qui crée la saison bascule sur sa nouvelle fiche."""
        nom = self._valider(db, ecole_id, nom, date_debut, date_fin)
        if duplication.cours and not duplication.profs:
            raise ErreurSaison("Pour recopier les cours, recopiez aussi les professeurs")
        if duplication.eleves and not duplication.cours:
            raise ErreurSaison("Pour recopier les élèves, recopiez aussi les cours")

        with toutes_saisons(db):
            ancienne_id = saison_courante_id(db, ecole_id)
            saison = Saison(ecole_id=ecole_id, nom=nom, date_debut=date_debut, date_fin=date_fin)
            db.add(saison)
            db.flush()
            fiches = self._recopier_comptes(db, ecole_id, ancienne_id, saison.id, duplication)
            if duplication.cours:
                self._recopier_cours(db, ancienne_id, saison, fiches, duplication.eleves)
            db.commit()
        db.refresh(saison)
        return saison, fiches

    # --- Détails ---

    def _valider(
        self,
        db: Session,
        ecole_id: int,
        nom: str,
        date_debut: dt.date,
        date_fin: dt.date,
        sauf_id: int | None = None,
    ) -> str:
        nom = (nom or "").strip()
        if not nom:
            raise ErreurSaison("Le nom de la saison est obligatoire")
        if date_fin <= date_debut:
            raise ErreurSaison("La date de fin doit être après la date de début")
        homonyme = db.scalar(select(Saison).where(Saison.ecole_id == ecole_id, Saison.nom == nom))
        if homonyme is not None and homonyme.id != sauf_id:
            raise ErreurSaison(f"Une saison « {nom} » existe déjà")
        return nom

    def _recopier_comptes(
        self, db: Session, ecole_id: int, ancienne_id: int, nouvelle_id: int, duplication: Duplication
    ) -> dict[int, int]:
        """Admins toujours ; profs et élèves selon les cases. Un admin qui
        était aussi professeur ou élève n'est recopié qu'en admin si la case
        correspondante n'est pas cochée (§2.6). Familles recopiées telles
        quelles pour les fiches reprises ; paiement remis à zéro."""
        roles_repris = {r.ADMIN, r.OWNER}
        if duplication.profs:
            roles_repris.add(r.PROFESSEUR)
        if duplication.eleves:
            roles_repris.add(r.ELEVE)

        familles: dict[int, Famille] = {}
        fiches: dict[int, int] = {}
        anciens = db.scalars(
            select(Compte).where(Compte.ecole_id == ecole_id, Compte.saison_id == ancienne_id).order_by(Compte.id)
        )
        for ancien in anciens:
            roles = [role for role in _ORDRE_ROLES if r.a_le_role(ancien, role) and role in roles_repris]
            if not roles:
                continue
            if ancien.famille_id not in familles:
                familles[ancien.famille_id] = Famille(ecole_id=ecole_id, saison_id=nouvelle_id)
                db.add(familles[ancien.famille_id])
            nouveau = Compte(
                ecole_id=ecole_id,
                saison_id=nouvelle_id,
                famille=familles[ancien.famille_id],
                compte_precedent_id=ancien.id,
                nom=ancien.nom,
                prenom=ancien.prenom,
                email=ancien.email,
                telephone=ancien.telephone,
                hashed_password_ou_code=ancien.hashed_password_ou_code,
                code_recuperation=ancien.code_recuperation,
            )
            nouveau.roles = [RoleCompte(role=role) for role in roles]
            db.add(nouveau)
            db.flush()
            fiches[ancien.id] = nouveau.id
            if r.ELEVE in roles:
                self._recopier_fiche_eleve(db, ancien.id, nouveau.id)
        return fiches

    def _recopier_fiche_eleve(self, db: Session, ancien_id: int, nouveau_id: int) -> None:
        profil = db.get(ProfilEleve, ancien_id)
        if profil is not None:
            # Paiement (statut, montants, commentaire) : valeurs par défaut,
            # propre à chaque saison.
            db.add(
                ProfilEleve(
                    compte_id=nouveau_id,
                    date_naissance=profil.date_naissance,
                    adresse=profil.adresse,
                    allergies=profil.allergies,
                    traitement_medical=profil.traitement_medical,
                    informations_importantes=profil.informations_importantes,
                )
            )
        for contact in db.scalars(select(ContactEleve).where(ContactEleve.eleve_id == ancien_id)):
            db.add(
                ContactEleve(
                    eleve_id=nouveau_id,
                    nom=contact.nom,
                    prenom=contact.prenom,
                    lien=contact.lien,
                    telephone=contact.telephone,
                    email=contact.email,
                )
            )

    def _recopier_cours(
        self, db: Session, ancienne_id: int, saison: Saison, fiches: dict[int, int], avec_eleves: bool
    ) -> None:
        """Cours et leurs horaires, avec les mêmes professeurs et, si demandé,
        les mêmes élèves. Présences, chorégraphies, vidéos et conversations
        ne sont jamais recopiées."""
        anciens = list(db.scalars(select(Cours).where(Cours.saison_id == ancienne_id).order_by(Cours.ordre, Cours.id)))
        nouveaux: dict[int, int] = {}
        for ancien in anciens:
            nouveau = Cours(
                ecole_id=ancien.ecole_id,
                saison_id=saison.id,
                nom=ancien.nom,
                jour=ancien.jour,
                heure_debut=ancien.heure_debut,
                heure_fin=ancien.heure_fin,
                salle=ancien.salle,
                descriptif=ancien.descriptif,
                ordre=ancien.ordre,
                horaires_supplementaires=[
                    CoursHoraireSupplementaire(jour=h.jour, heure_debut=h.heure_debut, heure_fin=h.heure_fin)
                    for h in ancien.horaires_supplementaires
                ],
            )
            db.add(nouveau)
            db.flush()
            nouveaux[ancien.id] = nouveau.id
        if not nouveaux:
            return

        liaisons = [(cours_professeurs, "professeur_id")]
        if avec_eleves:
            liaisons.append((eleves_cours, "eleve_id"))
        for table, colonne in liaisons:
            lignes = db.execute(select(table).where(table.c.cours_id.in_(nouveaux.keys()))).all()
            for ligne in lignes:
                personne = fiches.get(getattr(ligne, colonne))
                if personne is not None:
                    db.execute(table.insert().values(cours_id=nouveaux[ligne.cours_id], **{colonne: personne}))
