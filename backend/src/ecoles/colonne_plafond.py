"""Filet de sécurité au démarrage (plafond mensuel de l'assistant, Seb,
16 octobre) : ajoute la colonne `ecoles.assistant_plafond_mensuel_usd` si
la migration Alembic a1c3e5f7b9d2 n'est pas encore passée. Sans ça, toute
lecture d'une école échouerait (create_all n'ajoute pas de colonne à une
table qui existe)."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def ajouter_colonne_plafond(engine: Engine) -> None:
    with engine.begin() as connexion:
        if "assistant_plafond_mensuel_usd" in {c["name"] for c in inspect(connexion).get_columns("ecoles")}:
            return
        connexion.execute(text("ALTER TABLE ecoles ADD COLUMN assistant_plafond_mensuel_usd FLOAT NOT NULL DEFAULT 10"))
        logger.warning("Colonne ecoles.assistant_plafond_mensuel_usd ajoutée au démarrage")
