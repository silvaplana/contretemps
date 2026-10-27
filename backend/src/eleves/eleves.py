"""Logique métier des élèves (voir spec/SPEC.md §6.4). S'appuie sur
`comptes` pour les champs communs (nom/prénom/email...) — ne les duplique
pas, ne fait qu'ajouter `ProfilEleve`/`ContactEleve` par-dessus.
"""

from __future__ import annotations

import datetime as dt

from choregraphies.models import choregraphies_eleves
from comptes import Compte, Comptes, RegleRoles, roles
from comptes.models import RoleCompte, separer_emails
from groups import courses
from members import values as member_values
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ContactEleve, ProfilEleve


# Les anciens champs de `profils_eleves` devenus des champs de la fiche
# (spec/core.md §4.3, étape 4c) : nom ici → clé cachée du champ. Les
# colonnes restent dans la table, plus lues ni écrites.
CHAMPS_FICHE = {
    "date_naissance": "birth_date",
    "adresse": "address",
    "allergies": "allergies",
    "traitement_medical": "medical_treatment",
    "informations_importantes": "important_info",
}


def champs_fiche(reponses: dict[str, object]) -> dict[str, object]:
    """Les réponses {clé: réponse} d'une fiche sous les noms d'ici, la date
    de naissance en `datetime.date`."""
    champs = {nom: reponses.get(cle) for nom, cle in CHAMPS_FICHE.items()}
    champs["date_naissance"] = member_values.birth_date(reponses)
    return champs


def calculer_age(date_naissance: dt.date | None, aujourdhui: dt.date | None = None) -> int | None:
    """Âge calculé, jamais stocké (voir §6.4 : "*(Âge)* — Calculé")."""
    if date_naissance is None:
        return None
    aujourdhui = aujourdhui or dt.date.today()
    age = aujourdhui.year - date_naissance.year
    if (aujourdhui.month, aujourdhui.day) < (date_naissance.month, date_naissance.day):
        age -= 1
    return age


class Eleves:
    def __init__(self, comptes: Comptes) -> None:
        self.comptes = comptes

    def list(self, db: Session, ecole_id: int) -> list[Compte]:
        return self.comptes.list_par_role(db, ecole_id, role="eleve")

    def get_compte(self, db: Session, eleve_id: int) -> Compte | None:
        compte = self.comptes.get(db, eleve_id)
        if compte is None or not roles.is_eleve(compte):
            return None
        return compte

    def get_profil(self, db: Session, eleve_id: int) -> ProfilEleve | None:
        return db.get(ProfilEleve, eleve_id)

    def get_champs(self, db: Session, compte: Compte) -> dict[str, object]:
        """Date de naissance, adresse, santé : les réponses de la fiche."""
        return champs_fiche(member_values.known_of(db, compte))

    def champs_de_l_ecole(self, db: Session, ecole_id: int, saison_id: int) -> dict[int, dict[str, object]]:
        """Pareil pour toutes les fiches de la saison, en une fois : {fiche: champs}."""
        return {
            compte_id: champs_fiche(reponses)
            for compte_id, reponses in member_values.known_values(db, ecole_id, saison_id).items()
        }

    def _enregistrer_champs(self, db: Session, compte: Compte, champs: dict) -> None:
        """Retire de `champs` ceux de la fiche et les enregistre (sans commit ;
        FieldError si une réponse ne va pas)."""
        for nom, cle in CHAMPS_FICHE.items():
            if nom in champs:
                member_values.set_known(db, compte, cle, champs.pop(nom))

    def create(
        self,
        db: Session,
        ecole_id: int,
        nom: str,
        prenom: str,
        email: str | None = None,
        telephone: str | None = None,
        date_naissance: dt.date | None = None,
        **profil_champs,
    ) -> tuple[Compte, ProfilEleve]:
        """Une personne = une fiche (spec/core.md §4) : si la personne a déjà
        une fiche dans l'école sans être élève (un prof, un admin), on la
        complète au lieu d'en créer une autre."""
        compte = self._fiche_a_completer(db, ecole_id, nom, prenom, email)
        if compte is not None:
            if email:
                compte.definir_emails(compte.emails + separer_emails(email))
            compte.telephone = compte.telephone or telephone
            compte.roles.append(RoleCompte(role=roles.ELEVE))
            db.commit()
            self.comptes.recalculer_familles(db, ecole_id)
        else:
            compte = self.comptes.create(
                db,
                ecole_id=ecole_id,
                role="eleve",
                nom=nom,
                prenom=prenom,
                email=email,
                telephone=telephone,
            )
        profil_champs["date_naissance"] = date_naissance
        self._enregistrer_champs(db, compte, profil_champs)
        profil = ProfilEleve(compte_id=compte.id, **profil_champs)
        db.add(profil)
        db.commit()
        db.refresh(profil)
        return compte, profil

    def _fiche_a_completer(self, db: Session, ecole_id: int, nom: str, prenom: str, email: str | None) -> Compte | None:
        """La seule fiche non élève à ce nom et prénom. Jamais celle d'un
        admin qui recevrait une adresse nouvelle : cette adresse obtiendrait
        ses droits ; un Administrateur principal fusionne alors les deux
        fiches lui-même (Fusion)."""
        fiches = [c for c in self.comptes.trouver_par_nom_prenom(db, ecole_id, nom, prenom) if not roles.is_eleve(c)]
        if len(fiches) != 1:
            return None
        fiche = fiches[0]
        if roles.is_admin(fiche) and not set(separer_emails(email)) <= set(fiche.emails):
            return None
        return fiche

    def delete(self, db: Session, eleve_id: int) -> bool:
        """Supprime le profil + les contacts avant le compte lui-même
        (voir comptes.py : le socle commun ne connaît pas ProfilEleve)."""
        compte = self.get_compte(db, eleve_id)
        if compte is None:
            return False
        # Un élève peut être administrateur principal (§2.4) : le supprimer
        # ne doit jamais laisser l'école sans administrateur principal.
        if roles.is_owner(compte) and self.comptes.est_seul_owner(db, compte):
            raise RegleRoles("C'est le dernier administrateur principal de l'école : nommez-en d'abord un autre")
        for contact in self.contacts_de_leleve(db, eleve_id):
            db.delete(contact)
        # Même ménage que CoursService.delete : ses cours (groupes) et
        # `choregraphies_eleves` sont de simples tables de jointure, que
        # rien ne nettoie tout seul (SQLite tourne sans clés étrangères
        # actives). Sans ça, les inscriptions survivent à l'élève — vu en
        # production : 4 lignes pour 2 comptes supprimés — et un futur
        # élève en hériterait en silence si SQLite réutilise son id (pas
        # de mot-clé AUTOINCREMENT). Présences et messages, eux, sont
        # volontairement conservés : c'est de l'historique.
        courses.leave_all(db, eleve_id)
        db.execute(
            choregraphies_eleves.delete().where(choregraphies_eleves.c.eleve_id == eleve_id)
        )
        profil = self.get_profil(db, eleve_id)
        if profil is not None:
            db.delete(profil)
        db.commit()
        return self.comptes.delete(db, eleve_id)

    def update_profil(self, db: Session, eleve_id: int, **champs) -> ProfilEleve | None:
        profil = self.get_profil(db, eleve_id)
        if profil is None:
            return None
        # `champs` ne contient déjà que les champs explicitement fournis
        # (exclude_unset=True côté receiver) — un `if valeur is not None`
        # ici empêchait à tort de vider un champ nullable (ex. effacer une
        # allergie une fois résolue).
        compte = self.comptes.get(db, eleve_id)
        self._enregistrer_champs(db, compte, champs)
        for cle, valeur in champs.items():
            setattr(profil, cle, valeur)
        db.commit()
        db.refresh(profil)
        return profil

    # --- Contacts (voir §6.4 : plusieurs contacts possibles par élève) ---

    def contacts_de_leleve(self, db: Session, eleve_id: int) -> list[ContactEleve]:
        return list(
            db.scalars(select(ContactEleve).where(ContactEleve.eleve_id == eleve_id))
        )

    def ajouter_contact(self, db: Session, eleve_id: int, **champs) -> ContactEleve:
        contact = ContactEleve(eleve_id=eleve_id, **champs)
        db.add(contact)
        db.commit()
        db.refresh(contact)
        return contact

    def modifier_contact(self, db: Session, contact_id: int, **champs) -> ContactEleve | None:
        contact = db.get(ContactEleve, contact_id)
        if contact is None:
            return None
        # `champs` ne contient déjà que les champs explicitement fournis
        # (exclude_unset=True côté receiver) — un `if valeur is not None`
        # ici empêchait à tort de vider un champ nullable.
        for cle, valeur in champs.items():
            setattr(contact, cle, valeur)
        db.commit()
        db.refresh(contact)
        return contact

    def supprimer_contact(self, db: Session, contact_id: int) -> bool:
        contact = db.get(ContactEleve, contact_id)
        if contact is None:
            return False
        db.delete(contact)
        db.commit()
        return True
