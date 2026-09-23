"""Schémas des routes des saisons (voir receiver.py)."""

import datetime as dt

from pydantic import BaseModel, ConfigDict


class SaisonSortie(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    date_debut: dt.date
    date_fin: dt.date
    # La plus récente de l'école (§2.6), seule modifiable.
    courante: bool = False


class SaisonModification(BaseModel):
    nom: str
    date_debut: dt.date
    date_fin: dt.date


class SaisonCreation(SaisonModification):
    # Cases de duplication, dans cet ordre (§2.6) ; admins toujours recopiés.
    dupliquer_profs: bool = False
    dupliquer_cours: bool = False
    dupliquer_eleves: bool = False


class SaisonCreee(BaseModel):
    saison: SaisonSortie
    # Nouvelle fiche de l'admin qui a créé la saison : l'appli bascule
    # dessus aussitôt (sa fiche actuelle vient de passer en lecture seule).
    compte_id: int | None = None


class SaisonSupprimee(BaseModel):
    # Fiche à utiliser désormais par l'admin qui a supprimé la saison :
    # sa fiche de la saison précédente s'il vient de supprimer la courante
    # (donc la sienne), None s'il n'en a pas.
    compte_id: int | None = None
