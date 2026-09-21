"""Crée le Superuser, propriétaire de l'application (voir spec/SPEC.md §2.5),
ou change son mot de passe s'il existe déjà (même email).

SEULE façon de créer ce compte : jamais depuis l'appli. À lancer sur le
serveur, dans le conteneur backend :

    docker compose exec backend python -m app.creer_superuser

Le mot de passe est demandé au clavier, sans écho, et deux fois — jamais
passé en paramètre de la commande (il resterait dans l'historique du
terminal). Seule son empreinte (scrypt, voir securite/mots_de_passe.py) est
enregistrée.
"""

from __future__ import annotations

import getpass
import sys

import ecoles.models  # noqa: F401  (table "ecoles", référencée par comptes)
from comptes import Comptes
from db import SessionLocal
from securite import mots_de_passe

LONGUEUR_MIN = 10


def _demander(libelle: str) -> str:
    valeur = input(f"{libelle} : ").strip()
    if not valeur:
        sys.exit(f"{libelle} obligatoire.")
    return valeur


def main() -> None:
    print("Création (ou mise à jour) du Superuser — propriétaire de l'application.")
    prenom = _demander("Prénom")
    nom = _demander("Nom")
    email = _demander("Email")
    mot_de_passe = getpass.getpass(f"Mot de passe (au moins {LONGUEUR_MIN} caractères) : ")
    if len(mot_de_passe) < LONGUEUR_MIN:
        sys.exit(f"Mot de passe trop court (au moins {LONGUEUR_MIN} caractères).")
    if getpass.getpass("Mot de passe, à nouveau : ") != mot_de_passe:
        sys.exit("Les deux mots de passe ne correspondent pas.")

    db = SessionLocal()
    try:
        compte = Comptes().enregistrer_superuser(
            db, nom=nom, prenom=prenom, email=email, mot_de_passe_hache=mots_de_passe.hacher(mot_de_passe)
        )
    finally:
        db.close()
    print(f"Superuser enregistré : {compte.prenom} {compte.nom} <{compte.email}> (compte n° {compte.id}).")
    print("Connexion : même écran que tout le monde, ce mot de passe dans le champ « Code ».")


if __name__ == "__main__":
    main()
