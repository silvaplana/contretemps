"""Branchement du module `notes_frais` sur Contretemps : organisation = école,
personne = premier compte de la chaîne des saisons (comme pour documents),
trésorier = rôle `tresorier` (toujours un admin), adresses de l'école
(contact, trésorerie), mails par le SMTP de l'appli, notifications push.
"""

from __future__ import annotations

import logging
import os
from copy import copy
from pathlib import Path

from fastapi import Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from comptes import Compte, rbac, roles
from db import get_db
from documents_contretemps.adapter import _saison_courante, nom_affiche, personne_id
from notes_frais.ports import Membre, OperationBancaire, Organisation, Personne
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


# Le Super User n'a pas de fiche dans les écoles (spec/core.md §6.1) : il
# dit dans quelle école il intervient par cet en-tête, et sa note est à son
# nom (son compte), sans fiche créée pour lui.
ENTETE_ECOLE = "X-Ecole-Id"


def _ecole_choisie(db: Session, request: Request) -> int | None:
    from ecoles.models import Ecole

    valeur = request.headers.get(ENTETE_ECOLE, "")
    return int(valeur) if valeur.isdigit() and db.get(Ecole, int(valeur)) is not None else None


def membre_appelant(
    request: Request, db: Session = Depends(get_db), compte: Compte = Depends(rbac.compte_appelant)
) -> Membre:
    if compte is None:
        raise HTTPException(status_code=401, detail="Session requise")
    ecole_id = _ecole_choisie(db, request) if roles.is_superuser(compte) else compte.ecole_id
    if ecole_id is None:
        raise HTTPException(status_code=403, detail="Choisissez d'abord une école")
    return Membre(
        person_id=personne_id(db, compte),
        org_id=ecole_id,
        nom=nom_affiche(compte),
        emails=_emails(compte),
        est_tresorier=roles.is_tresorier(compte),
        est_superuser=roles.is_superuser(compte),
    )


def _personne(db: Session, compte: Compte) -> Personne:
    # Un prof qui est aussi admin reste un prof : c'est lui qu'on paie en
    # honoraires (Seb, 31/10).
    role = roles.PROFESSEUR if roles.is_prof(compte) else compte.role_principal if roles.noms_roles(compte) else ""
    return Personne(
        person_id=personne_id(db, compte),
        nom=nom_affiche(compte),
        emails=tuple(compte.emails),
        notification_id=compte.id,
        role=_LIBELLES.get(role, ""),
    )


def _cloturee(db: Session, org_id: int, jour) -> bool:
    """La saison qui contient ce jour est clôturée au Financier (financier.md §8.7)."""
    from finances.models import FinClosing

    return db.scalar(
        select(FinClosing.id).where(
            FinClosing.org_id == org_id, FinClosing.start_date <= jour, FinClosing.end_date >= jour, FinClosing.reopened_at.is_(None)
        )
    ) is not None


def _saison_contenant(db: Session, org_id: int, le):
    """La saison de l'école qui contient ce jour ; None sans jour ou hors de
    toute saison."""
    from saisons.models import Saison

    if le is None:
        return None
    with toutes_saisons(db):
        return db.scalar(
            select(Saison).where(Saison.ecole_id == org_id, Saison.date_debut <= le, Saison.date_fin >= le)
            .order_by(Saison.date_debut.desc())
        )


class AnnuaireContretemps:
    def _comptes_courants(self, db: Session, ecole_id: int, le=None) -> list[Compte]:
        """Les fiches de la saison courante ; `le` : celles de la saison qui
        contient ce jour, si elle existe."""
        contenant = _saison_contenant(db, ecole_id, le)
        saison = contenant.id if contenant is not None else _saison_courante(db, ecole_id)
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
            if compte is not None and (compte.ecole_id == org_id or roles.is_superuser(compte)):
                # Plus inscrite cette saison : pas de notification dans l'appli.
                resultat[pid] = Personne(pid, nom_affiche(compte), tuple(compte.emails), None)
        return resultat

    def tresoriers(self, db: Session, org_id: int) -> list[Personne]:
        return [_personne(db, c) for c in self._comptes_courants(db, org_id) if roles.is_tresorier(c)]

    def toutes(self, db: Session, org_id: int, le=None) -> list[Personne]:
        """Les personnes de toutes les saisons, une fois chacune : la fiche
        de la saison de `le` d'abord, sinon celle de la saison courante,
        sinon la plus récente (Seb, 1er/11 : une prof de l'an dernier doit
        être reconnue même quand la date de la facture n'a pas été lue)."""
        from saisons.models import Saison

        contenant = _saison_contenant(db, org_id, le)
        preferees = [s for s in ((contenant.id if contenant else None), _saison_courante(db, org_id)) if s is not None]
        with toutes_saisons(db):
            comptes = list(
                db.scalars(
                    select(Compte).join(Saison, Saison.id == Compte.saison_id)
                    .where(Compte.ecole_id == org_id).order_by(Saison.date_debut.desc())
                )
            )
        comptes.sort(key=lambda c: preferees.index(c.saison_id) if c.saison_id in preferees else len(preferees))
        personnes: dict[int, Personne] = {}
        for compte in comptes:
            personne = _personne(db, compte)
            personnes.setdefault(personne.person_id, personne)
        return sorted(personnes.values(), key=lambda p: p.nom.casefold())

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
    """Range les justificatifs dans Docs › Privé › Saison de la pièce ›
    Financier › Notes de frais, Honoraires ou Achats (§7 bis, financier.md
    §8.3 bis), par le module documents. Le dossier Financier est réservé aux
    trésoriers (dossier système, voir documents.md §4.7 bis)."""

    DOSSIER = "Notes de frais"
    # Les racines de pièces sous Financier (les anciens noms gardés : des
    # pièces y sont déjà rangées), jamais retirées quand elles se vident.
    DOSSIERS = ("Notes de frais", "HONORAIRES", "ACHATS", "Honoraires", "Achats")

    def __init__(self, documents, financier: str = "Financier") -> None:
        self.documents = documents
        self.financier = financier

    @staticmethod
    def _qui(qui: Membre):
        """Le membre (droits des trésoriers) sous lequel l'appli range."""
        from documents.ports import Member

        return Member(
            person_id=qui.agissant_id or qui.person_id,
            org_id=qui.org_id,
            display_name=qui.nom,
            is_admin=True,
            groups=frozenset({"role:admin", "role:tresorier"}),
            writes_closed_periods=True,
        )

    @staticmethod
    def _saison(db: Session, org_id: int, le):
        """La saison qui contient la date de la pièce, tant qu'elle n'est pas
        clôturée au Financier (Seb, 1er/11 : les trésoriers travaillent sur
        l'ancienne saison pendant la nouvelle, sans rien rouvrir dans Admin ›
        Saisons) ; None : la saison en cours."""
        saison = _saison_contenant(db, org_id, le)
        if saison is None or _cloturee(db, org_id, le):
            return None
        return saison.id

    def _acces(self, db: Session, qui: Membre, le=None):
        """Le dossier Financier de la saison de la pièce, et le membre."""
        racine = self.documents.reserved_folder(db, qui.org_id, self.financier, self._saison(db, qui.org_id, le))
        if racine is None:
            logger.warning("Pas de dossier %s pour l'école %s : pièce non rangée", self.financier, qui.org_id)
        return racine, self._qui(qui)

    @staticmethod
    def _enfant(db: Session, parent_id: int, nom: str, dossier: bool = True):
        from documents.models import KIND_FOLDER, DocNode

        requete = select(DocNode).where(DocNode.parent_id == parent_id, DocNode.deleted_at.is_(None))
        if dossier:
            # « Achats » déjà là (ancien nom, ou créé à la main) : on y écrit,
            # au lieu de créer « ACHATS (2) » à côté (Seb, 1er/11).
            requete = requete.where(DocNode.kind == KIND_FOLDER, func.lower(DocNode.name) == nom.lower())
        else:
            requete = requete.where(DocNode.name == nom)
        return db.scalars(requete).first()

    def _dossier(self, db: Session, qui, parent_id: int, chemin: list[str]) -> int:
        """Le dossier `chemin` sous `parent_id`, créé au besoin."""
        for nom in chemin:
            existant = self._enfant(db, parent_id, nom)
            parent_id = existant.id if existant is not None else self.documents.create_folder(db, qui, "private", parent_id, nom)["id"]
        return parent_id

    def classer(
        self, db: Session, membre: Membre, chemin: list[str], fichiers: list, remplacer=frozenset(), reprendre=False,
        le=None,
    ) -> list[int]:
        racine, qui = self._acces(db, membre, le)
        if racine is None:
            return []

        parent_id = self._dossier(db, qui, racine.id, chemin)
        ids = []
        for nom, chemin_fichier in fichiers:
            existant = self._enfant(db, parent_id, nom, dossier=False) if reprendre or nom in remplacer else None
            if existant is not None and nom not in remplacer:
                ids.append(existant.id)
                continue
            with open(chemin_fichier, "rb") as source:
                if existant is not None:
                    self.documents.new_version(db, qui, existant.id, nom, source)
                    ids.append(existant.id)
                else:
                    ids.append(self.documents.upload(db, qui, "private", parent_id, nom, source)["id"])
        return ids

    def deplacer(self, db: Session, membre: Membre, chemin: list[str], fichiers: list, le=None) -> None:
        from documents.models import DocNode

        racine, qui = self._acces(db, membre, le)
        if racine is None:
            return
        parent_id = self._dossier(db, qui, racine.id, chemin)
        quittes = set()
        for node_id, nom in fichiers:
            noeud = db.get(DocNode, node_id)
            if noeud is None or noeud.deleted_at is not None:
                continue
            # Un nom libre ici et là-bas : « nom (2) » comme au rangement.
            base, extension = Path(nom).stem, Path(nom).suffix
            libre, n = nom, 1
            while libre != noeud.name and any(
                (autre := self._enfant(db, dossier, libre, dossier=False)) is not None and autre.id != noeud.id
                for dossier in {parent_id, noeud.parent_id}
            ):
                n += 1
                libre = f"{base} ({n}){extension}"
            if noeud.parent_id != parent_id:
                quittes.add(noeud.parent_id)
            self.documents.update(db, qui, node_id, name=libre, parent_id=parent_id, move=noeud.parent_id != parent_id)
        for dossier_id in quittes:
            dossier = db.get(DocNode, dossier_id)
            vide = db.scalar(select(DocNode.id).where(DocNode.parent_id == dossier_id, DocNode.deleted_at.is_(None))) is None
            # A folder right under Financier may be a chosen place (financier.md §8.13): kept.
            if dossier is not None and dossier.name not in self.DOSSIERS and dossier.parent_id != racine.id and vide:
                self.documents.delete(db, qui, dossier_id)

    def sous_dossiers(self, db: Session, membre: Membre, chemin: list[str]) -> list[str]:
        from documents.models import KIND_FOLDER, DocNode

        racine, _ = self._acces(db, membre)
        if racine is None:
            return []
        noeud = racine
        for nom in chemin:
            noeud = self._enfant(db, noeud.id, nom)
            if noeud is None:
                return []
        return sorted(db.scalars(select(DocNode.name).where(
            DocNode.parent_id == noeud.id, DocNode.kind == KIND_FOLDER, DocNode.deleted_at.is_(None),
        )), key=str.lower)

    def contenu(self, db: Session, membre: Membre, node_id: int) -> Path:
        from documents.service import DocError

        try:
            chemin, _, _ = self.documents.content(db, self._qui(membre), node_id)
        except DocError as erreur:
            raise LookupError("Justificatif introuvable dans les documents.") from erreur
        return chemin

    def retirer(self, db: Session, membre: Membre, chemin: list[str], node_ids=(), le=None) -> None:
        racine, qui = self._acces(db, membre, le)
        if racine is None:
            return
        if node_ids:
            for node_id in node_ids:
                self.documents.delete(db, qui, node_id)
            return
        noeud = racine
        for nom in chemin:
            noeud = self._enfant(db, noeud.id, nom)
            if noeud is None:
                return
        self.documents.delete(db, qui, noeud.id)


class BanqueContretemps:
    """Les opérations des comptes du module Financier (financier.md §3), pour
    voir un virement passer sur le compte (§8.3 bis)."""

    def _requete(self, org_id: int):
        from finances.models import FinAccount, FinOperation

        return (
            select(FinOperation, FinAccount)
            .join(FinAccount, FinOperation.account_id == FinAccount.id)
            .where(FinAccount.org_id == org_id)
        )

    @staticmethod
    def _operation(operation, compte) -> OperationBancaire:
        return OperationBancaire(operation.id, operation.date, operation.label, operation.amount, compte.name, compte.ledger_number or "")

    def debits(self, db: Session, org_id: int, montant_centimes: int, depuis) -> list[OperationBancaire]:
        from finances.models import FinOperation

        requete = self._requete(org_id).where(FinOperation.amount == -montant_centimes, FinOperation.date >= depuis)
        return [self._operation(o, c) for o, c in db.execute(requete.order_by(FinOperation.date))]

    def tous_debits(self, db: Session, org_id: int, depuis) -> list[OperationBancaire]:
        from finances.models import FinOperation

        requete = self._requete(org_id).where(FinOperation.amount < 0, FinOperation.date >= depuis)
        return [self._operation(o, c) for o, c in db.execute(requete.order_by(FinOperation.date))]

    def operation(self, db: Session, org_id: int, operation_id: int) -> OperationBancaire | None:
        from finances.models import FinOperation

        ligne = db.execute(self._requete(org_id).where(FinOperation.id == operation_id)).first()
        return self._operation(*ligne) if ligne else None

    def cloturee(self, db: Session, org_id: int, jour) -> bool:
        return _cloturee(db, org_id, jour)

    # --- Ventes (financier.md §8.12) ---

    def credits(self, db: Session, org_id: int, montant_centimes: int, depuis) -> list[OperationBancaire]:
        from finances.models import FinOperation

        requete = self._requete(org_id).where(
            FinOperation.amount == montant_centimes, FinOperation.date >= depuis, FinOperation.transfer_id.is_(None)
        )
        return [self._operation(o, c) for o, c in db.execute(requete.order_by(FinOperation.date))]

    def tous_credits(self, db: Session, org_id: int, depuis) -> list[OperationBancaire]:
        from finances.models import FinOperation

        requete = self._requete(org_id).where(FinOperation.amount > 0, FinOperation.date >= depuis, FinOperation.transfer_id.is_(None))
        return [self._operation(o, c) for o, c in db.execute(requete.order_by(FinOperation.date))]

    @staticmethod
    def _comptes(db: Session, org_id: int, lignes: list[tuple[str, int]]) -> list[tuple[int | None, int]]:
        """(id du compte du plan, centimes) ; None pour une ligne sans compte connu."""
        from finances.models import FinChartAccount

        par_numero = {a.number: a.id for a in db.scalars(select(FinChartAccount).where(FinChartAccount.org_id == org_id))}
        return [(par_numero.get(numero), montant) for numero, montant in lignes]

    def ventiler(self, db: Session, org_id: int, operation_id: int, lignes, person_id: int) -> None:
        from finances.models import FinOperation, FinOperationAccount

        operation = db.get(FinOperation, operation_id)
        existantes = list(db.scalars(select(FinOperationAccount).where(FinOperationAccount.operation_id == operation_id)))
        if operation is None or any(not l.auto for l in existantes):
            return  # le compte déjà confirmé dans Comptes reste
        comptes = self._comptes(db, org_id, lignes)
        # Une ligne sans compte, ou une somme qui ne fait pas la banque : rien n'est confirmé, l'écart se voit.
        if any(a is None for a, _ in comptes) or sum(m for _, m in comptes) != operation.amount:
            return
        for ligne in existantes:  # un compte posé automatiquement cède à la pièce
            db.delete(ligne)
        db.add_all(FinOperationAccount(operation_id=operation_id, account_id=a, amount=m, confirmed_by=person_id) for a, m in comptes)
        db.commit()

    def deventiler(self, db: Session, org_id: int, operation_id: int, lignes) -> None:
        from finances.models import FinOperationAccount

        existantes = list(db.scalars(
            select(FinOperationAccount).where(FinOperationAccount.operation_id == operation_id).order_by(FinOperationAccount.id)
        ))
        if sorted((l.account_id, l.amount) for l in existantes) != sorted(self._comptes(db, org_id, lignes), key=lambda c: (c[0] or 0, c[1])):
            return  # changées depuis dans Comptes : on n'y touche pas
        for ligne in existantes:
            db.delete(ligne)
        db.commit()

    def entrer_en_caisse(self, db: Session, org_id: int, jour, libelle: str, lignes, person_id: int) -> None:
        from finances.models import FinCashLine

        db.add_all(
            FinCashLine(org_id=org_id, date=jour, label=libelle[:120], amount=m, account_id=a, created_by=person_id)
            for a, m in self._comptes(db, org_id, lignes)
        )
        db.commit()

    def sortir_de_caisse(self, db: Session, org_id: int, jour, libelle: str) -> None:
        from finances.models import FinCashLine

        for ligne in db.scalars(select(FinCashLine).where(FinCashLine.org_id == org_id, FinCashLine.date == jour, FinCashLine.label == libelle[:120])):
            db.delete(ligne)
        db.commit()


def comptes_de_charges(db: Session, org_id: int) -> list[tuple[str, str]]:
    """Les catégories des dépenses = les comptes de charges actifs du plan
    comptable du Financier (Seb, 30/10 ; financier.md §8.2)."""
    from finances.models import EXPENSE, FinChartAccount

    return [
        (a.number, a.label)
        for a in db.scalars(
            select(FinChartAccount).where(FinChartAccount.org_id == org_id, FinChartAccount.nature == EXPENSE, FinChartAccount.active.is_(True))
        )
    ]


def creer_compte(db: Session, org_id: int, numero: str, libelle: str, recette: bool) -> None:
    """Le compte proposé par la lecture (financier.md §8.2 bis), ajouté au
    plan du Financier ; déjà là mais inactif, il est réactivé."""
    from finances.models import EXPENSE, INCOME, FinChartAccount

    compte = db.scalar(select(FinChartAccount).where(FinChartAccount.org_id == org_id, FinChartAccount.number == numero))
    if compte is None:
        db.add(FinChartAccount(org_id=org_id, number=numero, label=libelle[:80], nature=INCOME if recette else EXPENSE, keywords=[]))
    elif (compte.nature == INCOME) != recette:
        raise ValueError(f"Le compte {numero} existe déjà comme compte de {'charges' if recette else 'produits'}.")
    else:
        compte.active = True
    db.commit()


def comptes_de_produits(db: Session, org_id: int) -> list[tuple[str, str]]:
    """Les comptes d'une vente = les comptes de produits actifs du plan
    comptable du Financier (financier.md §8.12)."""
    from finances.models import INCOME, FinChartAccount

    return [
        (a.number, a.label)
        for a in db.scalars(
            select(FinChartAccount).where(FinChartAccount.org_id == org_id, FinChartAccount.nature == INCOME, FinChartAccount.active.is_(True))
        )
    ]



# Les comptes d'un bulletin de salaire (financier.md §8.11) : numéro, libellé, nature.
_COMPTES_PAIE = (("641", "Salaires", "depense"), ("645", "Charges sociales", "depense"), ("431", "URSSAF à payer", "tiers"))


def comptes_paie_manquants(db: Session, org_id: int) -> list[tuple[str, str]]:
    """Les comptes de la paie absents (ou inactifs) du plan comptable."""
    from finances.models import FinChartAccount

    actifs = set(db.scalars(select(FinChartAccount.number).where(FinChartAccount.org_id == org_id, FinChartAccount.active.is_(True))))
    return [(numero, libelle) for numero, libelle, _ in _COMPTES_PAIE if numero not in actifs]


def ajouter_comptes_paie(db: Session, org_id: int) -> None:
    """Ajoute (ou réactive) les comptes de la paie. Le prélèvement de
    l'URSSAF solde 431 : le mot URSSAF passe de 645 à 431 pour que l'appli
    propose 431 sur ce prélèvement (sinon les cotisations compteraient deux fois)."""
    from finances.models import FinChartAccount

    comptes = {a.number: a for a in db.scalars(select(FinChartAccount).where(FinChartAccount.org_id == org_id))}
    for numero, libelle, nature in _COMPTES_PAIE:
        compte = comptes.get(numero)
        if compte is None:
            compte = FinChartAccount(org_id=org_id, number=numero, label=libelle, nature=nature, keywords=[])
            db.add(compte)
            comptes[numero] = compte
        compte.active = True
    if "URSSAF" not in (comptes["431"].keywords or []):
        comptes["431"].keywords = [*(comptes["431"].keywords or []), "URSSAF"]
    comptes["645"].keywords = [k for k in (comptes["645"].keywords or []) if k.upper() != "URSSAF"]
    db.commit()


def retirer_comptes_paie(db: Session, org_id: int) -> None:
    """« L'association a des salariés » : non. 431 devient inactif (jamais
    supprimé : il a pu servir) et le mot URSSAF revient sur 645."""
    from finances.models import FinChartAccount

    comptes = {a.number: a for a in db.scalars(select(FinChartAccount).where(FinChartAccount.org_id == org_id))}
    if "431" in comptes:
        comptes["431"].active = False
    if "645" in comptes and "URSSAF" not in [k.upper() for k in comptes["645"].keywords or []]:
        comptes["645"].keywords = [*(comptes["645"].keywords or []), "URSSAF"]
    db.commit()


def compte_de_tiers(db: Session, org_id: int, nature: str, nom: str) -> tuple[str, str] | None:
    """Le compte de tiers d'une pièce au niveau Complet, comme le Grand livre
    le prendra (financier.md §8.7) : 401 pour un achat, le 467n au nom de la
    personne pour des honoraires ou une note de frais. Un prof sans compte
    d'honoraires en aura un à la validation (numéro vide)."""
    from finances.ag_documents import THIRD_PARTY_PREFIX, _named, _third_party
    from finances.models import FinChartAccount, FinSettings

    reglage = db.get(FinSettings, org_id)
    if reglage is None or reglage.level != "complet" or nature not in THIRD_PARTY_PREFIX:
        return None
    comptes = list(db.scalars(
        select(FinChartAccount).where(FinChartAccount.org_id == org_id, FinChartAccount.active.is_(True))
    ))
    compte = _third_party(comptes, {"nature": nature, "person": nom})
    if nature == "honoraires" and nom and (compte is None or not _named(compte, nom)):
        return "", f"Honoraires {nom} (nouveau compte)"
    return (compte.number, compte.label) if compte is not None else None
