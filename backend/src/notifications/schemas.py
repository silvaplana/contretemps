"""Formes des requêtes/réponses HTTP (Pydantic) — pas les tables (voir
models.py). Les noms suivent ceux de l'API navigateur (PushSubscription
JSON, voir MDN) plutôt que la convention snake_case du reste du backend :
c'est exactement ce que `PushSubscription.toJSON()` envoie côté frontend,
inutile de le traduire.
"""

from pydantic import BaseModel


class ClesEntree(BaseModel):
    p256dh: str
    auth: str


class AbonnementEntree(BaseModel):
    endpoint: str
    keys: ClesEntree


class ClePubliqueSortie(BaseModel):
    # None si aucune clé VAPID configurée (voir .env.example) — le
    # frontend doit alors renoncer silencieusement à proposer les
    # notifications plutôt que d'échouer bruyamment.
    cle_publique: str | None
