from .database import Base, SessionLocal, engine, get_db

# Rattachement automatique à la saison courante (voir saisons/automatique.py) :
# importé ici pour être actif partout où la base est utilisée (appli, tests,
# commandes serveur), sans dépendre d'un point d'entrée précis. Après les
# noms ci-dessus, dont saisons/ a besoin.
import saisons.automatique  # noqa: E402,F401

__all__ = ["Base", "SessionLocal", "engine", "get_db"]
