"""Branchement du module `finances` sur Contretemps : organisation = école,
trésorier = rôle `tresorier`, Super User = école choisie (en-tête
X-Ecole-Id, comme pour les notes de frais), saisons = celles de l'école."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from comptes import Compte, rbac, roles
from db import get_db
from documents_contretemps.adapter import nom_affiche, personne_id
from finances.ports import Member, Season
from inscriptions.models import Inscription
from notes_frais_contretemps.adapter import _ecole_choisie
from saisons.models import Saison
from saisons.portee import toutes_saisons


# Le droit « Accès au Financier » (spec/core.md §5.3), déclaré dans module.py.
FINANCES_ACCESS = roles.DROIT_FINANCIER

def membre_appelant(
    request: Request, db: Session = Depends(get_db), compte: Compte = Depends(rbac.compte_appelant)
) -> Member:
    if compte is None:
        raise HTTPException(status_code=401, detail="Session requise")
    ecole_id = _ecole_choisie(db, request) if roles.is_superuser(compte) else compte.ecole_id
    if ecole_id is None:
        raise HTTPException(status_code=403, detail="Choisissez d'abord une école")
    return Member(
        person_id=personne_id(db, compte),
        org_id=ecole_id,
        name=nom_affiche(compte),
        is_treasurer=roles.has_right(compte, FINANCES_ACCESS),
        is_superuser=roles.is_superuser(compte),
    )


def saisons_de_l_ecole(db: Session, ecole_id: int) -> list[Season]:
    """De la plus ancienne à la plus récente, par dates ; la courante est
    celle de saisons/saisons.py (une saison passée peut être créée après
    coup, par exemple par l'import d'un vieux relevé)."""
    from saisons.saisons import saison_courante_id

    with toutes_saisons(db):
        saisons = list(db.scalars(select(Saison).where(Saison.ecole_id == ecole_id).order_by(Saison.date_debut, Saison.id)))
        courante = saison_courante_id(db, ecole_id)
    # Inscrits par saison : les fiches d'inscription de l'école.
    inscrits = dict(
        db.execute(
            select(Inscription.saison_id, func.count()).where(Inscription.ecole_id == ecole_id).group_by(Inscription.saison_id)
        ).all()
    )
    return [
        Season(
            id=s.id,
            name=s.nom,
            start_date=s.date_debut.isoformat(),
            end_date=s.date_fin.isoformat(),
            current=s.id == courante,
            members=inscrits.get(s.id, 0),
        )
        for s in saisons
    ]


def adresse_ecole(db: Session, ecole_id: int | None) -> str:
    """L'adresse de l'appli de l'école (son sous-domaine), où revenir après
    la banque (connexion bancaire, finances/bank.py) ; l'adresse générale si
    l'école est inconnue."""
    from auth.mails import MailsAcces
    from ecoles.models import Ecole

    ecole = db.get(Ecole, ecole_id) if ecole_id is not None else None
    return MailsAcces().appli(ecole.sous_domaine if ecole is not None else None)


# Libellés des natures de dépense (notes_frais/models.py) sur la ligne de Comptes.
_NATURES = {"frais": "Note de frais", "honoraires": "Honoraires", "achat": "Achat"}


def pieces_des_operations(db: Session, ecole_id: int) -> dict[int, dict]:
    """La pièce rattachée à chaque opération bancaire (spec financier.md
    §8.4) : les dépenses du module Notes de frais payées par cette opération
    (`nf_notes.bank_operation_id`)."""
    from notes_frais.models import NoteFrais

    notes = list(
        db.scalars(select(NoteFrais).where(NoteFrais.org_id == ecole_id, NoteFrais.bank_operation_id.is_not(None)))
    )
    noms = {}
    with toutes_saisons(db):
        for compte in db.scalars(select(Compte).where(Compte.id.in_({n.person_id for n in notes}))):
            noms[compte.id] = nom_affiche(compte)
    return {
        n.bank_operation_id: {
            "id": n.id,
            "title": n.supplier or n.titre,
            "kind": _NATURES.get(n.nature, n.nature),
            "nature": n.nature,
            # Date de la facture (première dépense), sinon de l'envoi : l'achat du jour de la facture (§8.7).
            "date": min((d.date for d in n.depenses), default=n.envoyee_le.date()).isoformat(),
            "person": noms.get(n.person_id, ""),
        }
        for n in notes
    }


def pieces_a_payer(db: Session, ecole_id: int) -> list[dict]:
    """Les dépenses validées pas encore payées (fournisseurs à payer de la
    Synthèse, spec §8.6) : titre et montant en euros."""
    from notes_frais.models import PREPAREE, VALIDEE, VIREE, NoteFrais
    from notes_frais.service import NotesDeFrais

    notes = db.scalars(
        select(NoteFrais).where(
            NoteFrais.org_id == ecole_id, NoteFrais.don.is_(False), NoteFrais.statut.in_((VALIDEE, PREPAREE, VIREE))
        )
    )
    return [{"title": n.supplier or n.titre, "amount": NotesDeFrais.total(n) / 100} for n in notes]


def honoraires_payes(db: Session, ecole_id: int, debut: str, fin: str) -> list[dict]:
    """Les notes d'honoraires payées sur la période (date du paiement vu sur
    le compte, sinon date du remboursement) : prof, mois (AAAA-MM), montant
    en euros, pour le relevé DAS-2 (spec §8.6)."""
    from finances.models import FinOperation
    from notes_frais.models import HONORAIRES, REMBOURSEE, NoteFrais
    from notes_frais.service import NotesDeFrais

    notes = list(
        db.scalars(
            select(NoteFrais).where(NoteFrais.org_id == ecole_id, NoteFrais.nature == HONORAIRES, NoteFrais.statut == REMBOURSEE)
        )
    )
    noms = {}
    with toutes_saisons(db):
        for compte in db.scalars(select(Compte).where(Compte.id.in_({n.person_id for n in notes}))):
            noms[compte.id] = nom_affiche(compte)
    resultat = []
    for n in notes:
        operation = db.get(FinOperation, n.bank_operation_id) if n.bank_operation_id else None
        jour = operation.date.isoformat() if operation is not None else (n.remboursee_le.date().isoformat() if n.remboursee_le else None)
        if jour is None or not debut <= jour <= fin:
            continue
        resultat.append({"person": noms.get(n.person_id, f"Personne {n.person_id}"), "month": jour[:7], "amount": NotesDeFrais.total(n) / 100})
    return resultat


def nom_ecole(db: Session, ecole_id: int) -> str:
    from ecoles.models import Ecole

    ecole = db.get(Ecole, ecole_id)
    return ecole.nom if ecole is not None else ""


def dossier_ag(documents):
    """Le dossier Docs › Privé › Saison en cours › Financier › AG (créé au
    besoin), pour le bouton « Ouvrir dans Docs » des documents de l'AG."""
    from notes_frais.ports import Membre
    from notes_frais_contretemps.adapter import ClasseurContretemps

    classeur = ClasseurContretemps(documents)

    def trouver(db: Session, member: Member) -> int | None:
        membre = Membre(person_id=member.person_id, org_id=member.org_id, nom=member.name, est_tresorier=True)
        racine, qui = classeur._acces(db, membre)
        if racine is None:
            return None
        return classeur._dossier(db, qui, racine.id, ["AG"])

    return trouver


def ranger_dans_docs(documents):
    """Range les documents de l'AG dans Docs › Privé › Saison en cours ›
    Financier › AG, par le classeur des notes de frais (même dossier Financier)."""
    from notes_frais.ports import Membre
    from notes_frais_contretemps.adapter import ClasseurContretemps

    classeur = ClasseurContretemps(documents)

    def ranger(db: Session, member: Member, chemin: list[str], fichiers: list) -> list[int]:
        membre = Membre(person_id=member.person_id, org_id=member.org_id, nom=member.name, est_tresorier=True)
        return classeur.classer(db, membre, chemin, fichiers, remplacer={nom for nom, _ in fichiers})

    return ranger


RELEVES = "RELEVES BANCAIRES"


def _dossier_majuscules(nom: str) -> str:
    """Nom de dossier en majuscules sans accent (règle de Seb, 30/10)."""
    from notes_frais.stockage import nom_dossier

    return nom_dossier(nom)


def ranger_releve(documents, gestion_saisons):
    """Range le PDF d'un relevé importé dans Docs › Privé › Saison du relevé
    (celle de sa date de fin) › Financier › RELEVES BANCAIRES › <nom du
    compte>. Une saison passée absente est créée (septembre à août, comme une
    saison créée après coup dans Admin › Saisons) ; une saison terminée et
    fermée ne reçoit rien : à rouvrir dans Admin › Saisons."""
    import datetime as dt
    import tempfile
    from pathlib import Path

    from notes_frais.ports import Membre
    from notes_frais_contretemps.adapter import ClasseurContretemps
    from saisons.gestion import Duplication, ErreurSaison
    from saisons.saisons import saison_courante_id, saison_par_defaut

    classeur = ClasseurContretemps(documents)

    def ranger(db: Session, member: Member, compte: str, fin: str, nom: str, contenu: bytes) -> str | None:
        le = dt.date.fromisoformat(fin)
        with toutes_saisons(db):
            saison = db.scalar(
                select(Saison).where(Saison.ecole_id == member.org_id, Saison.date_debut <= le, Saison.date_fin >= le)
            )
            courante = db.get(Saison, saison_courante_id(db, member.org_id))
        if saison is None and courante is not None and le < courante.date_debut:
            nom_saison, debut, fin_saison = saison_par_defaut(le)
            try:
                saison, _ = gestion_saisons.creer(db, member.org_id, nom_saison, debut, fin_saison, Duplication())
            except ErreurSaison as erreur:
                return f"PDF non rangé dans Docs ({erreur})"
        saison = saison or courante
        if saison is None:
            return None
        if saison.id != (courante.id if courante else None) and not saison.ouverte:
            return f"PDF non rangé : la saison {saison.nom} est fermée (Admin › Saisons › rouvrir, puis réimporter)"
        racine = documents.reserved_folder(db, member.org_id, "Financier", saison.id)
        if racine is None:
            return None
        membre = Membre(person_id=member.person_id, org_id=member.org_id, nom=member.name, est_tresorier=True)
        qui = classeur._qui(membre)
        dossier = classeur._dossier(db, qui, racine.id, [RELEVES, _dossier_majuscules(compte)])
        existant = classeur._enfant(db, dossier, nom, dossier=False)
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / nom
            chemin.write_bytes(contenu)
            with open(chemin, "rb") as source:
                if existant is not None:
                    documents.new_version(db, qui, existant.id, nom, source)
                else:
                    documents.upload(db, qui, "private", dossier, nom, source)
        return f"rangé dans Docs › {saison.nom} › Financier › {RELEVES} › {_dossier_majuscules(compte)}"

    return ranger


VENTES = ("COTISATIONS", "COURS", "PARTICIPATION GALA")


def preparer_dossiers_financier(documents):
    """Crée, vides, les dossiers de la trésorière sous Financier (Seb, 30/10)
    dans la saison en cours et les saisons ouvertes : RELEVES BANCAIRES ›
    un par compte en banque, ACHATS (ses mois viennent avec les pièces),
    HONORAIRES › un par prof (PRENOM NOM), VENTES › COTISATIONS, COURS,
    PARTICIPATION GALA. Une fois par saison et par processus : ce qui existe
    déjà ne bouge pas."""
    from comptes.roles import PROFESSEUR, a_le_role
    from finances.models import FinAccount
    from notes_frais.ports import Membre
    from notes_frais.stockage import nom_dossier
    from notes_frais_contretemps.adapter import ClasseurContretemps
    from saisons.saisons import saison_courante_id

    classeur = ClasseurContretemps(documents)
    faits: set[tuple[int, int, tuple]] = set()

    def preparer(db: Session, member: Member) -> None:
        with toutes_saisons(db):
            courante = saison_courante_id(db, member.org_id)
            saisons = [
                s for s in db.scalars(select(Saison).where(Saison.ecole_id == member.org_id))
                if s.id == courante or s.ouverte
            ]
        comptes = sorted({_dossier_majuscules(a.name) for a in db.scalars(select(FinAccount).where(FinAccount.org_id == member.org_id))})
        membre = Membre(person_id=member.person_id, org_id=member.org_id, nom=member.name, est_tresorier=True)
        qui = classeur._qui(membre)
        for saison in saisons:
            with toutes_saisons(db):
                profs = sorted({
                    nom_dossier(nom_affiche(c))
                    for c in db.scalars(select(Compte).where(Compte.ecole_id == member.org_id, Compte.saison_id == saison.id))
                    if a_le_role(c, PROFESSEUR)
                })
            cle = (member.org_id, saison.id, (*comptes, "|", *profs))
            if cle in faits:
                continue
            racine = documents.reserved_folder(db, member.org_id, "Financier", saison.id)
            if racine is None:
                continue
            chemins = [[RELEVES], *([RELEVES, c] for c in comptes), ["ACHATS"], ["HONORAIRES"],
                       *(["HONORAIRES", p] for p in profs), *(["VENTES", v] for v in VENTES)]
            for chemin in chemins:
                classeur._dossier(db, qui, racine.id, chemin)
            db.commit()
            faits.add(cle)

    return preparer
