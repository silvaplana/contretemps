"""Schémas des routes des saisons (voir receiver.py)."""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict


class SaisonSortie(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    date_debut: dt.date
    date_fin: dt.date
    # Celle qui commence le plus tard (§2.6), toujours modifiable.
    courante: bool = False
    # Ancienne saison ouverte exceptionnellement aux modifications.
    ouverte: bool = False


class SaisonModification(BaseModel):
    nom: str
    date_debut: dt.date
    date_fin: dt.date


class SaisonOuverture(BaseModel):
    ouverte: bool


class SaisonCreation(SaisonModification):
    # Cases de duplication, dans cet ordre (§2.6) ; admins toujours recopiés.
    dupliquer_profs: bool = False
    dupliquer_cours: bool = False
    dupliquer_eleves: bool = False
    # Onglet Docs : recopier le dossier de la saison précédente.
    dupliquer_documents: bool = False
    # La fiche des élèves (spec/modules/saisons.md §3) : celle de la saison
    # précédente, ou la structure de base (sans les champs ajoutés par
    # l'école) ; et les champs (ids de la saison précédente) à masquer.
    structure_eleves: Literal["last", "base"] = "last"
    champs_masques: list[int] = []


class ChampContenu(BaseModel):
    id: int
    label: str
    # Clé des champs que l'appli sait lire (members.fields.KNOWN), sinon
    # None : un champ ajouté par l'école.
    key: str | None = None
    member_sees: bool = False
    others_see: bool = False


class SaisonContenu(BaseModel):
    """Ce que la nouvelle saison peut reprendre de la courante : les
    nombres des cases « Recopier… » et les champs de la fiche des élèves."""

    eleves: int
    profs: int
    cours: int
    champs: list[ChampContenu]


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
