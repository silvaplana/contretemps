"""Donne à une école le plan comptable de l'association Contretemps, repris
de la Balance 2024-25 de sa trésorière (spec/modules/financier.md §8.2) :
les comptes y sont ajoutés ou renommés, les comptes par défaut qui ne
servent à rien chez Contretemps (jamais utilisés) sont retirés. Les
ventilations déjà confirmées ne bougent pas.

À lancer sur le serveur, dans le conteneur backend :

    docker compose exec backend python -m app.plan_comptable_contretemps --ecole 1

`--essai` affiche ce qui serait fait, sans rien changer.
"""

from __future__ import annotations

import argparse

from sqlalchemy import select

from db import SessionLocal
from finances.models import EXPENSE, INCOME, SUSPENSE, THIRD_PARTY, FinChartAccount, FinOperationAccount

# (numéro, libellé, nature, mots-clés, événement)
PLAN_CONTRETEMPS = (
    ("6063", "Autres fournitures", EXPENSE, ("AMAZON", "TEMU", "ALI EXPRESS", "CASTORAMA", "IKEA", "DARTY"), None),
    ("6064", "Fournitures administratives", EXPENSE, ("BUREAU VALLEE", "ONLINEPRINTERS"), None),
    ("607", "Tissus, mercerie, accessoires", EXPENSE, ("MELLE DANSE", "MADEMOISELLE DANSE", "KIABI"), None),
    ("613", "Location Galli", EXPENSE, ("GALLI",), "gala"),
    ("6135", "Hébergement du site", EXPENSE, ("OVH", "IONOS"), None),
    ("615", "Entretien et réparations", EXPENSE, (), None),
    ("616", "Assurance MAIF", EXPENSE, ("MAIF",), None),
    ("622", "Intervenants (technicien, sécurité)", EXPENSE, ("POMPIER", "TECHNICIEN"), "gala"),
    ("6226", "Honoraires des professeurs", EXPENSE, ("REVELLES", "DE LUCA", "PESENTI", "THOMAS", "HONORAIRE"), None),
    ("6228", "Travaux de couture", EXPENSE, ("COUTURE",), "gala"),
    ("623", "Publicité", EXPENSE, ("FLYERS", "PICTURE IMPACT"), None),
    ("625", "Défraiement, gasoil", EXPENSE, ("TOTAL", "DEFRAIEMENT"), None),
    ("6257", "Réception, sortie", EXPENSE, ("CARREFOUR", "AUCHAN", "RELAIS", "CAFE BLEU"), None),
    ("627", "Services bancaires", EXPENSE, ("FACT SGT", "COTIS CB", "FRAIS"), None),
    ("651", "SACEM / SPRE", EXPENSE, ("SACEM", "SPRE"), "gala"),
    ("658", "Charges diverses", EXPENSE, (), None),
    ("756", "Cotisations", INCOME, ("COTISATION",), None),
    ("7561", "Participation au gala", INCOME, ("GALA",), "gala"),
    ("7563", "Entrées Galli", INCOME, ("ENTREE",), "gala"),
    ("7567", "Cours", INCOME, ("REM CHQ", "HELLOASSO", "REMISE"), None),
    ("758", "Produits divers", INCOME, (), None),
    ("768", "Intérêts du livret", INCOME, ("INTERET",), None),
    ("401", "Fournisseurs", THIRD_PARTY, (), None),
    ("411", "Adhérents", THIRD_PARTY, (), None),
    ("4671", "Honoraires Revelles", THIRD_PARTY, (), None),
    ("46711", "Honoraires De Luca", THIRD_PARTY, (), None),
    ("4672", "Honoraires Pesenti", THIRD_PARTY, (), None),
    ("4679", "Honoraires Thomas", THIRD_PARTY, (), None),
    ("471", "Compte d'attente", SUSPENSE, (), None),
)


def appliquer(db, ecole_id: int, essai: bool = False) -> list[str]:
    """Applique le plan ; renvoie une ligne par changement."""
    existants = {a.number: a for a in db.scalars(select(FinChartAccount).where(FinChartAccount.org_id == ecole_id))}
    changements = []
    voulus = set()
    for numero, libelle, nature, mots, evenement in PLAN_CONTRETEMPS:
        voulus.add(numero)
        compte = existants.get(numero)
        if compte is None:
            changements.append(f"+ {numero} {libelle}")
            if not essai:
                db.add(FinChartAccount(org_id=ecole_id, number=numero, label=libelle, nature=nature, event=evenement, keywords=list(mots)))
            continue
        if (compte.label, compte.nature, compte.event, list(compte.keywords or [])) != (libelle, nature, evenement, list(mots)):
            changements.append(f"~ {numero} {compte.label} → {libelle}")
            if not essai:
                compte.label, compte.nature, compte.event, compte.keywords, compte.active = libelle, nature, evenement, list(mots), True
    for numero, compte in existants.items():
        if numero in voulus:
            continue
        utilise = db.scalar(select(FinOperationAccount.id).where(FinOperationAccount.account_id == compte.id).limit(1))
        changements.append(f"- {numero} {compte.label}" + (" (utilisé : passé inactif)" if utilise else ""))
        if not essai:
            if utilise:
                compte.active = False
            else:
                db.delete(compte)
    if not essai:
        db.commit()
    return changements


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--ecole", type=int, required=True, help="id de l'école")
    parser.add_argument("--essai", action="store_true", help="n'écrit rien, affiche seulement")
    args = parser.parse_args()
    with SessionLocal() as db:
        for ligne in appliquer(db, args.ecole, args.essai):
            print(ligne)
    print("(essai : rien n'a été écrit)" if args.essai else "Plan comptable appliqué.")


if __name__ == "__main__":
    main()
