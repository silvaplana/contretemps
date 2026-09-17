"""Indicateur "en train d'écrire" (voir spec/SPEC.md §5.5, demande
utilisateur du 2026-09-17) — état volontairement JAMAIS persisté :
une info qui n'a de sens qu'à l'instant présent, un redémarrage serveur
ou un event perdu suffit à l'effacer, ce qui est très bien. Aucun
signal explicite "j'ai arrêté d'écrire" n'est envoyé : le client qui
reçoit l'event fait lui-même expirer l'indicateur ~6s après le dernier
reçu (voir frontend/src/utils/frappeIndicateur.js).

Throttle CÔTÉ SERVEUR en plus du throttle client (voir
ConversationThreadScreen.jsx) : protège contre un client qui n'aurait
pas encore ce garde-fou (ancienne version en cache, bug) plutôt qu'une
vraie limite anti-abus.
"""

from __future__ import annotations

import time

DELAI_THROTTLE_SECONDES = 2.0


class Frappe:
    def __init__(self) -> None:
        self._dernier_envoi: dict[tuple[int, int], float] = {}

    def doit_publier(self, conversation_id: int, compte_id: int) -> bool:
        cle = (conversation_id, compte_id)
        maintenant = time.monotonic()
        dernier = self._dernier_envoi.get(cle)
        if dernier is not None and maintenant - dernier < DELAI_THROTTLE_SECONDES:
            return False
        self._dernier_envoi[cle] = maintenant
        return True
