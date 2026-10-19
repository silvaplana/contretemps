"""Action des notes de frais ouverte à l'assistant (spec/modules/assistant-ia.md §3) :
faire une note de frais, pour soi ou, pour un trésorier, pour quelqu'un
d'autre (comme Financier › ⋯ « pour quelqu'un »). Ici et pas dans
`notes_frais/` : il faut passer du compte de Contretemps au `Membre` du module.
"""

from __future__ import annotations

import datetime as dt

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

    return [
        Action("submit_expense_report", "Notes de frais",
               "Fait une note de frais et l'envoie aux trésoriers : une ou plusieurs dépenses, pour la personne elle-même "
               "ou, si elle est trésorière, pour quelqu'un d'autre. Les justificatifs s'ajoutent ensuite dans l'appli.",
               ExpenseReport, prepare, admin_only=False),
    ]
