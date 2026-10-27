"""Chiffrer un secret gardé en base (clé d'API d'une organisation, ex. la
clé secrète HelloAsso) : Fernet (AES + signature), avec une clé tirée du
secret du serveur (`jetons._secret`, variable SECRET_JETONS ou fichier du
volume persistant). Une base copiée sans ce secret ne livre pas les clés :
il faut alors les recoller."""

from __future__ import annotations

import base64
import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken

from .jetons import _secret


def _fernet() -> Fernet:
    cle = hmac.new(_secret(), b"chiffrement des secrets en base", hashlib.sha256).digest()
    return Fernet(base64.urlsafe_b64encode(cle))


def chiffrer(texte: str) -> str:
    return _fernet().encrypt(texte.encode("utf-8")).decode("ascii")


def dechiffrer(chiffre: str) -> str | None:
    """Le texte, ou None si le secret du serveur a changé depuis."""
    try:
        return _fernet().decrypt(chiffre.encode("ascii")).decode("utf-8")
    except InvalidToken:
        return None
