"""Mots de passe hachés (voir spec/SPEC.md §2.5 : le mot de passe du
Superuser n'est JAMAIS stocké en clair).

scrypt, de la bibliothèque standard (hashlib) : pas de dépendance en plus,
et c'est une fonction conçue pour les mots de passe (lente et gourmande en
mémoire exprès, pour rendre coûteux un essai en masse). Chaque mot de passe
a son propre sel aléatoire, stocké avec le résultat.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

# Paramètres scrypt recommandés pour une connexion interactive (≈ 16 Mo,
# une fraction de seconde) : assez lents pour décourager un essai en
# masse, assez rapides pour qu'on ne les sente pas à la connexion.
_N, _R, _P = 2**14, 8, 1
_PREFIXE = "scrypt"


def _b64(octets: bytes) -> str:
    return base64.b64encode(octets).decode("ascii")


def hacher(mot_de_passe: str) -> str:
    """Format stocké : scrypt$N$r$p$sel$empreinte (sel et empreinte en
    base64) — les paramètres voyagent avec, pour pouvoir les changer un
    jour sans casser les mots de passe existants."""
    sel = secrets.token_bytes(16)
    empreinte = hashlib.scrypt(mot_de_passe.encode("utf-8"), salt=sel, n=_N, r=_R, p=_P)
    return f"{_PREFIXE}${_N}${_R}${_P}${_b64(sel)}${_b64(empreinte)}"


def verifier(mot_de_passe: str, stocke: str | None) -> bool:
    if not stocke or not stocke.startswith(f"{_PREFIXE}$"):
        return False
    try:
        _, n, r, p, sel, empreinte = stocke.split("$")
        attendue = base64.b64decode(empreinte)
        calculee = hashlib.scrypt(
            mot_de_passe.encode("utf-8"), salt=base64.b64decode(sel), n=int(n), r=int(r), p=int(p)
        )
    except (ValueError, TypeError):
        return False
    # Comparaison à temps constant : ne pas révéler, par la durée, combien
    # de caractères de l'empreinte correspondent.
    return hmac.compare_digest(calculee, attendue)
