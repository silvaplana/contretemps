"""Filet de sécurité au démarrage (plusieurs emails par fiche, spec §6.3) :
si la table `emails_compte` est vide alors que l'ancienne colonne
`comptes.email` contient des adresses, elles y sont recopiées. Même travail
que la migration Alembic e5c7a9b1d3f4 : sans ça, un déploiement dont on
oublie la migration empêcherait toute connexion (le mot de passe se trouve
par l'email)."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from .models import separer_emails

logger = logging.getLogger(__name__)


def reprendre_anciens_emails(engine: Engine) -> None:
    with engine.begin() as connexion:
        if "email" not in {c["name"] for c in inspect(connexion).get_columns("comptes")}:
            return
        if connexion.execute(text("SELECT 1 FROM emails_compte LIMIT 1")).first() is not None:
            return
        lignes = [
            {"compte_id": compte_id, "email": email, "created_at": cree_le}
            for compte_id, brut, cree_le in connexion.execute(
                text("SELECT id, email, created_at FROM comptes WHERE email IS NOT NULL AND email <> ''")
            )
            for email in separer_emails(brut)
        ]
        if lignes:
            connexion.execute(
                text("INSERT INTO emails_compte (compte_id, email, created_at) VALUES (:compte_id, :email, :created_at)"),
                lignes,
            )
            logger.warning("Emails des fiches repris de comptes.email : %d adresses", len(lignes))
