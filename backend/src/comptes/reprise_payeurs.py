"""Reprise de l'email du payeur (spec/core.md §4.4, étape 5) : avant, une
famille = les fiches reliées de proche en proche par un email commun. Chaque
famille de plusieurs fiches reçoit comme email du payeur l'adresse que portent
le plus de ses fiches (celle du parent), pour garder exactement les mêmes
familles. Une fiche seule garde un email du payeur vide (= son premier email).
Même travail que la migration b9d1f3a5c7e8, et pour une sauvegarde d'avant."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection


def reprendre_payeurs(connexion: Connection, ecole_id: int | None = None) -> int:
    """Remplit `comptes.payer_email` des familles de plusieurs fiches qui
    n'en ont pas encore. Renvoie le nombre de fiches remplies."""
    filtre = "" if ecole_id is None else " AND c.ecole_id = :ecole"
    lignes = connexion.execute(
        text(
            "SELECT c.famille_id, c.id, e.email FROM comptes c "
            "LEFT JOIN emails_compte e ON e.compte_id = c.id "
            "WHERE c.famille_id IS NOT NULL AND c.payer_email IS NULL" + filtre + " ORDER BY c.id, e.id"
        ),
        {"ecole": ecole_id},
    ).all()
    familles: dict[int, dict[int, list[str]]] = {}
    for famille_id, compte_id, email in lignes:
        emails = familles.setdefault(famille_id, {}).setdefault(compte_id, [])
        if email:
            emails.append(email)
    remplies = 0
    for fiches in familles.values():
        if len(fiches) < 2:
            continue
        compte: dict[str, int] = {}
        for emails in fiches.values():
            for email in emails:
                compte[email] = compte.get(email, 0) + 1
        if not compte:
            continue
        # La plus portée ; à égalité, la première rencontrée (dict ordonné).
        payeur = max(compte, key=compte.get)
        connexion.execute(
            text("UPDATE comptes SET payer_email = :p WHERE id IN (" + ",".join(str(i) for i in fiches) + ")"),
            {"p": payeur},
        )
        remplies += len(fiches)
    return remplies
