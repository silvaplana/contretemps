import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Importe le moteur/Base partagé, et les modèles de chaque module (juste
# pour l'effet de bord : les enregistrer sur Base.metadata, nécessaire
# pour qu'`alembic revision --autogenerate` les voie). Un nouveau module
# avec ses propres tables s'ajoute simplement ici.
from choregraphies.models import Choregraphie, choregraphies_eleves  # noqa: F401
from comptes.models import Compte, Famille  # noqa: F401
from cours.models import Cours, cours_professeurs, eleves_cours  # noqa: F401
from db import Base
from ecoles.models import Ecole  # noqa: F401
from eleves.models import ContactEleve, ProfilEleve  # noqa: F401
from presence.models import PresenceEleve, PresenceProf, SeancePresence  # noqa: F401
from videos.models import Video  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Même variable d'environnement que db/database.py (pas de duplication de
# la config) : sqlite en local par défaut, Postgres en prod.
config.set_main_option(
    "sqlalchemy.url", os.environ.get("DATABASE_URL", "sqlite:///./contretemps.db")
)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
