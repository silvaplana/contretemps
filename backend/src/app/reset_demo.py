"""Remet la BDD et les fichiers vidéo dans un état de démo propre et
connu — à lancer (en local ou sur le VPS) après une session de test qui
a modifié la BDD/les fichiers, pour repartir de zéro au prochain
lancement (demande explicite de l'utilisateur, voir backend-architecture
côté mémoire projet).

⚠️ DESTRUCTIF : vide TOUTES les tables et TOUT le dossier vidéos "live"
avant de recréer les données de démo. Conçu pour un environnement de
démo/dev, jamais pour une base contenant de vraies données de production
— d'où la confirmation explicite requise (--yes).

Usage :
    python -m app.reset_demo --yes
"""

import argparse
import shutil

# Importés pour leur effet de bord : enregistrer toutes les tables sur
# Base.metadata avant drop_all/create_all (sinon SQLAlchemy ne voit que
# les modules déjà importés côté module courant — même piège que
# alembic/env.py, voir backend-architecture côté mémoire projet).
import choregraphies  # noqa: F401
import cours  # noqa: F401
import eleves  # noqa: F401
import messagerie  # noqa: F401
import presence  # noqa: F401
from db import Base, engine
from videos import DOSSIER_VIDEOS_LIVE, DOSSIER_VIDEOS_REFERENCE

from . import seed


def reset_base() -> None:
    """Supprime puis recrée toutes les tables (DB-agnostique, ne dépend
    pas de l'historique Alembic — cohérent avec le create_all déjà fait
    au démarrage de l'app, voir app/main.py)."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def reset_videos() -> None:
    """Vide le dossier vidéos "live" et le remplace par une copie du
    dossier de référence (voir videos/stockage.py) — vide pour l'instant
    tant que le stockage vidéo n'est pas encore utilisé en pratique."""
    if DOSSIER_VIDEOS_LIVE.exists():
        shutil.rmtree(DOSSIER_VIDEOS_LIVE)
    DOSSIER_VIDEOS_LIVE.mkdir(parents=True, exist_ok=True)
    if DOSSIER_VIDEOS_REFERENCE.exists():
        shutil.copytree(DOSSIER_VIDEOS_REFERENCE, DOSSIER_VIDEOS_LIVE, dirs_exist_ok=True)


def run() -> None:
    print("Réinitialisation de la base...")
    reset_base()
    print("Rejeu du seed de démo (école, comptes, cours, élèves)...")
    seed.run()
    print("Réinitialisation des vidéos...")
    reset_videos()
    print("Reset terminé.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirme l'opération (destructive) — sans ce drapeau, le reset est refusé.",
    )
    args = parser.parse_args()
    if not args.yes:
        print(
            "Refusé : opération destructive (vide la base et le dossier vidéos). "
            "Relancer avec --yes pour confirmer."
        )
        raise SystemExit(1)
    run()


if __name__ == "__main__":
    main()
