"""Branchement du module `notes_frais` sur Contretemps : organisation = école,
personne = premier compte de la chaîne des saisons (comme pour documents),
trésorier = rôle `tresorier` (toujours un admin), adresses de l'école
(contact, trésorerie), mails par le SMTP de l'appli, notifications push.
"""

from __future__ import annotations

import logging
import os
from copy import copy

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from comptes import Compte, rbac, roles
from db import get_db
from documents_contretemps.adapter import _saison_courante, nom_affiche, personne_id
from notes_frais.ports import Membre, Organisation, Personne
from saisons.portee import TOUTES_SAISONS, toutes_saisons

logger = logging.getLogger(__name__)

_LIBELLES = {"admin": "admin", "professeur": "prof", "eleve": "élève"}


def _emails(compte: Compte) -> tuple[str, ...]:
    # L'adresse de connexion d'abord : c'est celle des réponses.
    connecte = getattr(compte, "email_connecte", None)
    adresses = list(compte.emails)
    if connecte in adresses:
        adresses.remove(connecte)
        adresses.insert(0, connecte)
    return tuple(adresses)


def membre_appelant(db: Session = Depends(get_db), compte: Compte = Depends(rbac.compte_appelant)) -> Membre:
    if compte is None:
        raise HTTPException(status_code=401, detail="Session requise")
    if compte.ecole_id is None:
        raise HTTPException(status_code=403, detail="Choisissez d'abord une école")
    return Membre(
        person_id=personne_id(db, compte),
        org_id=compte.ecole_id,
        nom=nom_affiche(compte),
        emails=_emails(compte),
        est_tresorier=roles.is_tresorier(compte),
        est_superuser=roles.is_superuser(compte),
    )


def _personne(db: Session, compte: Compte) -> Personne:
    role = roles.role_principal(r.role for r in compte.roles) if compte.roles else ""
    return Personne(
        person_id=personne_id(db, compte),
        nom=nom_affiche(compte),
        emails=tuple(compte.emails),
        notification_id=compte.id,
        role=_LIBELLES.get(role, ""),
    )


class AnnuaireContretemps:
    def _comptes_courants(self, db: Session, ecole_id: int) -> list[Compte]:
        saison = _saison_courante(db, ecole_id)
        with toutes_saisons(db):
            return list(db.scalars(select(Compte).where(Compte.ecole_id == ecole_id, Compte.saison_id == saison)))

    def personnes(self, db: Session, org_id: int, person_ids: set[int]) -> dict[int, Personne]:
        """Chaque personne avec sa fiche de la saison courante (ses adresses
        d'aujourd'hui) ; à défaut, sa dernière fiche connue."""
        if not person_ids:
            return {}
        resultat: dict[int, Personne] = {}
        for compte in self._comptes_courants(db, org_id):
            personne = _personne(db, compte)
            if personne.person_id in person_ids:
                resultat[personne.person_id] = personne
        for pid in person_ids - resultat.keys():
            compte = db.get(Compte, pid, execution_options={TOUTES_SAISONS: True})
            if compte is not None and compte.ecole_id == org_id:
                # Plus inscrite cette saison : pas de notification dans l'appli.
                resultat[pid] = Personne(pid, nom_affiche(compte), tuple(compte.emails), None)
        return resultat

    def tresoriers(self, db: Session, org_id: int) -> list[Personne]:
        return [_personne(db, c) for c in self._comptes_courants(db, org_id) if roles.is_tresorier(c)]

    def organisation(self, db: Session, org_id: int) -> Organisation:
        from ecoles.models import Ecole
        from personnalisation.personnalisation import adresse_de_l_ecole

        ecole = db.get(Ecole, org_id)
        if ecole is None:
            return Organisation("Contretemps", os.environ.get("URL_APPLI", "https://silvaplana.cloud/contretemps").rstrip("/"))
        return Organisation(
            nom=ecole.nom,
            adresse_web=adresse_de_l_ecole(ecole).rstrip("/"),
            email_contact=ecole.email_contact,
            email_tresorier=ecole.email_tresorier,
        )


class MessagerContretemps:
    """Mails au nom de l'école, depuis l'adresse de l'appli (Brevo)."""

    def __init__(self) -> None:
        from inscriptions.email_envoi import EmailEnvoi

        self.envoi = EmailEnvoi()

    def envoyer(self, db: Session, org_id: int, a: list[str], sujet: str, texte: str, html: str, repondre_a: str | None) -> None:
        if not self.envoi.actif:
            logger.warning("Mail non envoyé (pas de SMTP) à %s : %s\n%s", a, sujet, texte)
            return
        org = AnnuaireContretemps().organisation(db, org_id)
        envoi = copy(self.envoi)
        envoi.nom_expediteur = org.nom
        envoi.repondre_a = repondre_a or org.email_contact or self.envoi.repondre_a
        for destinataire in a:
            try:
                envoi.envoyer_confirmation(destinataire, sujet, texte, [], html)
            except Exception:  # noqa: BLE001 - un destinataire en échec n'empêche pas les autres
                logger.exception("Mail de note de frais non envoyé à %s", destinataire)


class NotifieurContretemps:
    def __init__(self, notifications) -> None:
        self.notifications = notifications

    def notifier(self, db: Session, notification_id: int, titre: str, corps: str) -> None:
        self.notifications.envoyer_a_compte(db, notification_id, titre, corps)


class ClasseurContretemps:
    """Range les notes validées dans Docs › Privé › Saison en cours ›
    Financier › Notes de frais (§7 bis), par le module documents. Le dossier
    Financier est réservé aux trésoriers (dossier système, voir
    documents.md §4.7 bis)."""

    DOSSIER = "Notes de frais"

    def __init__(self, documents, financier: str = "Financier") -> None:
        self.documents = documents
        self.financier = financier

    def _acces(self, db: Session, qui: Membre):
        """Le dossier Financier de la saison en cours, et le membre (droits
        des trésoriers) sous lequel l'appli y range les notes."""
        from documents.ports import Member

        racine = self.documents.reserved_folder(db, qui.org_id, self.financier)
        if racine is None:
            logger.warning("Pas de dossier %s pour l'école %s : note non rangée", self.financier, qui.org_id)
        membre = Member(
            person_id=qui.person_id,
            org_id=qui.org_id,
            display_name=qui.nom,
            is_admin=True,
            groups=frozenset({"role:admin", "role:tresorier"}),
        )
        return racine, membre

    @staticmethod
    def _enfant(db: Session, parent_id: int, nom: str, dossier: bool = True):
        from documents.models import KIND_FOLDER, DocNode

        requete = select(DocNode).where(DocNode.parent_id == parent_id, DocNode.name == nom, DocNode.deleted_at.is_(None))
        if dossier:
            requete = requete.where(DocNode.kind == KIND_FOLDER)
        return db.scalars(requete).first()

    def classer(
        self, db: Session, membre: Membre, chemin: list[str], fichiers: list, statut: str, remplacer=frozenset()
    ) -> None:
        racine, qui = self._acces(db, membre)
        if racine is None:
            return

        def dossier(parent_id: int, nom: str) -> int:
            existant = self._enfant(db, parent_id, nom)
            if existant is not None:
                return existant.id
            return self.documents.create_folder(db, qui, "private", parent_id, nom)["id"]

        personne, nom_note = chemin
        note_id = dossier(dossier(dossier(racine.id, self.DOSSIER), personne), nom_note)
        for nom, chemin_fichier in fichiers:
            existant = self._enfant(db, note_id, nom, dossier=False)
            if existant is not None and nom not in remplacer:
                continue
            with open(chemin_fichier, "rb") as source:
                if existant is not None:
                    self.documents.new_version(db, qui, existant.id, nom, source)
                else:
                    self.documents.upload(db, qui, "private", note_id, nom, source)
        # Le dossier ne bouge plus : son badge dit où en est la note.
        self.documents.update(db, qui, note_id, status=statut, change_status=True)

    def retirer(self, db: Session, membre: Membre, chemin: list[str]) -> None:
        racine, qui = self._acces(db, membre)
        if racine is None:
            return
        noeud = self._enfant(db, racine.id, self.DOSSIER)
        for nom in chemin:
            if noeud is None:
                return
            noeud = self._enfant(db, noeud.id, nom)
        if noeud is not None:
            self.documents.delete(db, qui, noeud.id)
