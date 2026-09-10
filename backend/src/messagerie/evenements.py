"""Pub/sub en mémoire pour le flux temps réel de la messagerie (SSE, voir
spec/SPEC.md §5.5) : un compte connecté ouvre UN SEUL flux
(`GET /comptes/{id}/messagerie/evenements`, voir receiver.py) qui reçoit
tout nouveau message le concernant, quelle que soit la conversation — pas
un flux par conversation ouverte (choix explicite : sans ça, la LISTE des
conversations elle-même ne se mettrait à jour que pour le fil actuellement
ouvert, voir discussion côté spec).

Pas de Redis/message broker : un seul worker uvicorn (voir
backend/Dockerfile : `CMD ["python", "-m", "app.main"]`, pas de
`--workers`), donc un simple dict en mémoire suffit — à revoir si jamais
plusieurs process partagent la même API un jour.
"""

from __future__ import annotations

import asyncio


class Evenements:
    """⚠️ Thread-safety : les routes FastAPI *sync* (`def`, pas
    `async def` — c'est le cas de tout `receiver.py` dans ce backend)
    tournent dans un thread à part (Starlette : `run_in_threadpool`),
    jamais le thread de la boucle asyncio qui fait vivre les flux SSE.
    `publier()` doit donc passer par `loop.call_soon_threadsafe` plutôt
    que d'appeler `Queue.put_nowait` directement depuis ce thread-là —
    `asyncio.Queue` n'est pas thread-safe."""

    def __init__(self) -> None:
        self._abonnes: dict[int, list[asyncio.Queue]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def demarrer(self, loop: asyncio.AbstractEventLoop) -> None:
        """Appelé une fois, au démarrage de l'app (voir app/main.py) —
        capture la VRAIE boucle asyncio qui sert les requêtes. Ne PAS
        utiliser `asyncio.get_event_loop()` à l'import : ça peut créer
        une boucle différente de celle qu'uvicorn démarre réellement."""
        self._loop = loop

    def abonner(self, compte_id: int) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._abonnes.setdefault(compte_id, []).append(queue)
        return queue

    def desabonner(self, compte_id: int, queue: asyncio.Queue) -> None:
        abonnes = self._abonnes.get(compte_id)
        if not abonnes or queue not in abonnes:
            return
        abonnes.remove(queue)
        if not abonnes:
            self._abonnes.pop(compte_id, None)

    def publier(self, compte_id: int, evenement: dict) -> None:
        """Pousse `evenement` sur tous les flux ouverts de ce compte (0,
        1 ou plusieurs — plusieurs onglets/appareils connectés en même
        temps). Ne fait rien si le compte n'a aucun flux ouvert (pas
        d'erreur : c'est le cas normal la plupart du temps)."""
        abonnes = self._abonnes.get(compte_id)
        if not abonnes:
            return
        for queue in list(abonnes):
            if self._loop is not None:
                self._loop.call_soon_threadsafe(queue.put_nowait, evenement)
            else:
                # Pas encore démarré (ex. appelé depuis un test sans app
                # FastAPI réellement lancée) : on est déjà sur le bon
                # thread dans ce cas, put_nowait direct est sûr.
                queue.put_nowait(evenement)
