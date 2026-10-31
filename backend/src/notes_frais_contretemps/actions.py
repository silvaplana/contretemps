"""Actions des notes de frais ouvertes à l'assistant (spec/modules/assistant-ia.md §3) :
faire une note de frais, pour soi ou, pour un trésorier, pour quelqu'un
d'autre (comme Financier › ⋯ « pour quelqu'un »). Pour le trésorier (Seb,
30 octobre) : lire les pièces de Financier › Pièces, et valider ou refuser
d'un coup celles que l'assistant propose (une carte), marquer payées. Ici et
pas dans `notes_frais/` : il faut passer du compte de Contretemps au
`Membre` du module.
"""

from __future__ import annotations

import datetime as dt
import json

from assistant.actions import Action
from assistant.modifications import Ligne, Refus
from comptes import roles
from documents_contretemps.adapter import nom_affiche, personne_id
from notes_frais import NotesDeFrais
from notes_frais.ports import Membre
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .adapter import _emails


class Expense(BaseModel):
    date: dt.date = Field(description="Date de la dépense, AAAA-MM-JJ.")
    amount_euros: float = Field(gt=0, le=100_000, description="Montant TTC en euros.")
    description: str = Field(min_length=1, max_length=200, description="Ce qui a été acheté.")
    category: str | None = Field(default=None, description="Catégorie de l'association, ou null.")


class ExpenseReport(BaseModel):
    title: str = Field(min_length=1, max_length=120, description="Titre de la note, ex. « Costumes du gala ».")
    expenses: list[Expense] = Field(min_length=1, max_length=20)
    donation: bool = Field(default=False, description="true si la personne renonce au remboursement (don à l'association).")
    for_person: str | None = Field(
        default=None, description="Prénom et nom de la personne, si un trésorier fait la note pour quelqu'un d'autre ; null pour soi."
    )


class Pieces(BaseModel):
    filter: str = Field(
        default="a_valider",
        description="a_valider, a_rembourser, terminees, ou une nature : frais (notes de frais), honoraires, achat.",
    )


class Refusal(BaseModel):
    note_id: int
    reason: str = Field(min_length=1, max_length=2000, description="Motif du refus, envoyé à la personne.")


class Review(BaseModel):
    validate_ids: list[int] = Field(default_factory=list, max_length=50, description="Numéros des pièces à valider.")
    refuse: list[Refusal] = Field(default_factory=list, max_length=50, description="Pièces à refuser, avec leur motif.")


class Paid(BaseModel):
    note_ids: list[int] = Field(min_length=1, max_length=50, description="Numéros des pièces payées (virement fait).")


class Undo(BaseModel):
    note_ids: list[int] = Field(min_length=1, max_length=50, description="Numéros des pièces à ramener une étape en arrière.")


class Cancel(BaseModel):
    note_ids: list[int] = Field(min_length=1, max_length=50, description="Numéros des pièces à annuler (tout défaire).")


def _euros(centimes: int) -> str:
    return f"{centimes / 100:.2f}".replace(".", ",") + " €"


def actions(service: NotesDeFrais) -> list[Action]:
    def prepare(db: Session, compte, org_id: int, p: ExpenseReport) -> Ligne:
        membre = Membre(
            person_id=personne_id(db, compte), org_id=org_id, nom=nom_affiche(compte), emails=_emails(compte),
            est_tresorier=roles.is_tresorier(compte), est_superuser=roles.is_superuser(compte),
        )
        if p.for_person:
            cherche = " ".join(p.for_person.split()).casefold()
            personnes = service.personnes(db, membre)  # PermissionError hors trésoriers
            trouve = [x for x in personnes if x.nom.casefold() == cherche] or [x for x in personnes if cherche in x.nom.casefold()]
            if len(trouve) != 1:
                raise Refus(f"personne « {p.for_person} » " + ("introuvable" if not trouve else "ambiguë : " + ", ".join(x.nom for x in trouve)))
            membre = service.agir_pour(db, membre, trouve[0].person_id)
        categories = {c.libelle.casefold(): c.id for c in service.categories(db, org_id)}
        depenses = []
        for e in p.expenses:
            if e.date > dt.date.today():
                raise Refus(f"la dépense « {e.description} » est datée dans le futur")
            if e.category and e.category.casefold() not in categories:
                raise Refus(f"catégorie « {e.category} » inconnue. Catégories : {', '.join(c.libelle for c in service.categories(db, org_id))}")
            depenses.append((e, round(e.amount_euros * 100), categories.get((e.category or "").casefold())))
        if not p.donation and service.rib(db, org_id, membre.person_id) is None:
            raise Refus(f"pas de RIB enregistré pour {membre.nom} : il se saisit dans « Mes notes de frais », ou bien c'est un don")

        def faire(db: Session) -> None:
            ids = [
                service.creer_depense(db, membre, jour=e.date, montant_centimes=c, categorie_id=cat, description=e.description).id
                for e, c, cat in depenses
            ]
            service.envoyer(db, membre, depense_ids=ids, titre=p.title, don=p.donation)

        total = sum(c for _, c, _ in depenses)
        detail = " ; ".join(f"{e.description} {_euros(c)} le {e.date:%d/%m}" for e, c, _ in depenses)
        pour = f" pour {membre.nom}" if p.for_person else ""
        issue = "don à l'association" if p.donation else "remboursement sur le RIB enregistré"
        return Ligne(f"Envoyer la note « {p.title} »{pour} aux trésoriers : {_euros(total)} ({detail}), {issue}", faire)

    def tresorier(db: Session, compte, org_id: int) -> Membre:
        membre = Membre(
            person_id=personne_id(db, compte), org_id=org_id, nom=nom_affiche(compte), emails=_emails(compte),
            est_tresorier=roles.is_tresorier(compte), est_superuser=roles.is_superuser(compte),
        )
        if not membre.est_tresorier and not membre.est_superuser:
            raise PermissionError("réservé aux trésoriers")
        return membre

    def notes(db: Session, membre: Membre, ids) -> dict[int, dict]:
        par_id = {n["id"]: n for n in service.tresorerie(db, membre, "a_valider") + service.tresorerie(db, membre, "a_rembourser")}
        inconnues = [i for i in ids if i not in par_id]
        if inconnues:
            raise Refus(f"pièces {', '.join(map(str, inconnues))} introuvables ou plus en attente (voir expense_notes)")
        return par_id

    def lire(db: Session, compte, org_id: int, p: Pieces) -> str:
        membre = tresorier(db, compte, org_id)
        try:
            liste = service.tresorerie(db, membre, p.filter)
        except ValueError as erreur:
            raise Refus(str(erreur)) from erreur
        return json.dumps([
            {
                "id": n["id"], "title": n["titre"], "nature": n["nature"], "supplier": n["fournisseur"],
                "person": (n.get("personne") or {}).get("nom"), "status": n["libelle_statut"], "donation": n["don"],
                "total": n["total_centimes"] / 100, "sentOn": n["envoyee_le"][:10], "refusal": n["motif_refus"],
                "rib": bool(n["rib"]), "seenOnBankAccount": n.get("paiement_propose"),
                "expenses": [
                    {"date": d["date"], "amount": d["montant_centimes"] / 100, "description": d["description"],
                     "category": (d["categorie"] or {}).get("libelle"), "receipt": not d["sans_justificatif"],
                     "readFromPhoto": d["lue_par_ia"]}
                    for d in n["depenses"]
                ],
            }
            for n in liste
        ], ensure_ascii=False, separators=(",", ":"))

    def preparer_revue(db: Session, compte, org_id: int, p: Review) -> Ligne:
        membre = tresorier(db, compte, org_id)
        refus = {r.note_id: r.reason for r in p.refuse}
        if not p.validate_ids and not refus:
            raise Refus("rien à valider ni à refuser")
        if set(p.validate_ids) & set(refus):
            raise Refus("une même pièce ne peut pas être validée et refusée")
        par_id = notes(db, membre, [*p.validate_ids, *refus])
        for i in [*p.validate_ids, *refus]:
            if par_id[i]["statut"] != "envoyee":
                raise Refus(f"« {par_id[i]['titre']} » n'est plus à valider")

        def faire(db: Session) -> None:
            echecs = []
            for i in p.validate_ids:
                try:
                    service.valider(db, membre, i)
                except (ValueError, PermissionError) as erreur:
                    echecs.append(f"« {par_id[i]['titre']} » : {erreur}")
            for i, motif in refus.items():
                try:
                    service.refuser(db, membre, i, motif)
                except (ValueError, PermissionError) as erreur:
                    echecs.append(f"« {par_id[i]['titre']} » : {erreur}")
            if echecs:
                raise Refus("pas fait pour " + " ; ".join(echecs))

        def qui(n: dict) -> str:
            nom = (n.get("personne") or {}).get("nom") or n["fournisseur"] or ""
            return f"« {n['titre']} »" + (f" ({nom})" if nom else "") + f" {_euros(n['total_centimes'])}"

        parties = []
        if p.validate_ids:
            parties.append("Valider " + " ; ".join(qui(par_id[i]) for i in p.validate_ids))
        if refus:
            parties.append("Refuser " + " ; ".join(f"{qui(par_id[i])}, motif : {m}" for i, m in refus.items()))
        return Ligne(". ".join(parties) + ". Visible dans Financier › Pièces.", faire)

    def preparer_payees(db: Session, compte, org_id: int, p: Paid) -> Ligne:
        membre = tresorier(db, compte, org_id)
        par_id = notes(db, membre, p.note_ids)

        def faire(db: Session) -> None:
            try:
                service.rembourser(db, membre, p.note_ids)
            except (ValueError, PermissionError) as erreur:
                raise Refus(str(erreur)) from erreur

        return Ligne(
            "Marquer payées (virement fait) : " + " ; ".join(f"« {par_id[i]['titre']} » {_euros(par_id[i]['total_centimes'])}" for i in p.note_ids),
            faire,
        )

    ETAPE_AVANT = {"viree": "À payer", "preparee": "À payer", "validee": "À valider"}

    def preparer_retour(db: Session, compte, org_id: int, p: Undo) -> Ligne:
        membre = tresorier(db, compte, org_id)
        par_id = notes(db, membre, p.note_ids)
        for i in p.note_ids:
            if par_id[i]["statut"] not in ETAPE_AVANT:
                raise Refus(f"« {par_id[i]['titre']} » : rien à défaire" + (" (payée : la détacher d'abord de la ligne du compte)" if par_id[i]["statut"] == "remboursee" else ""))

        def faire(db: Session) -> None:
            for i in p.note_ids:
                try:
                    service.revenir(db, membre, i)
                except (ValueError, PermissionError) as erreur:
                    raise Refus(f"« {par_id[i]['titre']} » : {erreur}") from erreur

        return Ligne(
            "Revenir en arrière : " + " ; ".join(f"« {par_id[i]['titre']} » → {ETAPE_AVANT[par_id[i]['statut']]}" for i in p.note_ids),
            faire,
        )

    def preparer_annulation(db: Session, compte, org_id: int, p: Cancel) -> Ligne:
        membre = tresorier(db, compte, org_id)
        par_id = notes(db, membre, p.note_ids)
        for i in p.note_ids:
            if par_id[i]["statut"] == "remboursee" and par_id[i].get("operation_id"):
                raise Refus(f"« {par_id[i]['titre']} » est payée : la détacher d'abord de la ligne du compte")

        def faire(db: Session) -> None:
            for i in p.note_ids:
                try:
                    service.supprimer_note(db, membre, i)
                except (ValueError, PermissionError) as erreur:
                    raise Refus(f"« {par_id[i]['titre']} » : {erreur}") from erreur

        return Ligne(
            "Annuler (tout défaire) : " + " ; ".join(f"« {par_id[i]['titre']} » {_euros(par_id[i]['total_centimes'])}" for i in p.note_ids)
            + ". Les justificatifs vont à la corbeille ; une note envoyée par un membre lui revient.",
            faire,
        )

    return [
        Action("expense_notes", "Pièces",
               "Financier › Pièces (trésorier) : notes de frais, honoraires et achats, à valider, à payer ou terminés, avec "
               "leurs dépenses, justificatif présent ou non, RIB, paiement vu sur le compte. Pour proposer des validations : "
               "lire « a_valider », vérifier chaque pièce, expliquer, puis review_expense_notes.",
               Pieces, None, admin_only=False, read=lire),
        Action("review_expense_notes", "Pièces",
               "Valide et/ou refuse (avec motif) plusieurs pièces à valider en une seule carte, que le trésorier accepte ou non.",
               Review, preparer_revue, admin_only=False),
        Action("mark_expense_notes_paid", "Pièces",
               "Marque payées des pièces validées dont le virement est fait (sans attendre de le voir sur le compte).",
               Paid, preparer_payees, admin_only=False),
        Action("undo_expense_notes", "Pièces",
               "Ramène des pièces une étape en arrière (Envoyé ou Préparé → À payer, À payer → À valider). Jamais une pièce "
               "payée rattachée à la ligne du compte.",
               Undo, preparer_retour, admin_only=False),
        Action("cancel_expense_notes", "Pièces",
               "Annule des pièces faites par erreur, quel que soit leur état (tout défaire : justificatifs à la corbeille, une "
               "note envoyée par un membre lui revient). Jamais une pièce payée rattachée à la ligne du compte.",
               Cancel, preparer_annulation, admin_only=False),
        Action("submit_expense_report", "Notes de frais",
               "Fait une note de frais et l'envoie aux trésoriers : une ou plusieurs dépenses, pour la personne elle-même "
               "ou, si elle est trésorière, pour quelqu'un d'autre. Les justificatifs s'ajoutent ensuite dans l'appli.",
               ExpenseReport, prepare, admin_only=False),
    ]
