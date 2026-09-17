"""Présence "en ligne" / "dernière connexion" (voir spec/SPEC.md §5.5,
demande utilisateur du 2026-09-17) — à ne pas confondre avec l'écran
"Présence" (feuille de présence aux cours, module `presence/`), un tout
autre sens du mot, pur hasard de vocabulaire.

Vie privée (décision utilisateur du 2026-09-17) : visible entre TOUS les
comptes qui partagent déjà une conversation, y compris élève-élève —
volontairement pas restreint à l'équipe pédagogique pour l'instant.
`correspondants()` est le seul endroit qui décide "qui voit qui" :
restreindre plus tard (ex. masquer entre élèves) ne touchera que cette
fonction.

"En ligne maintenant" n'est JAMAIS persisté (voir evenements.py:
est_en_ligne) : dérivé du flux SSE réellement ouvert. Seule la
"dernière connexion" (Compte.derniere_activite_le) est écrite en base,
et seulement au moment où le DERNIER flux ouvert de ce compte se ferme
(voir sortie() ci-dessous) — pas à chaque déconnexion d'un simple 2e
onglet.
"""

from __future__ import annotations

from datetime import datetime, timezone

from comptes import Compte, Comptes
from sqlalchemy.orm import Session

from .conversations import Conversations
from .evenements import Evenements


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Connexions:
    def __init__(
        self, comptes: Comptes, conversations: Conversations, evenements: Evenements
    ) -> None:
        self.comptes = comptes
        self.conversations = conversations
        self.evenements = evenements

    def correspondants(self, db: Session, compte_id: int) -> list[Compte]:
        """Tous les comptes qui partagent au moins une conversation avec
        `compte_id` (lui excepté) — seuls destinataires de ses
        changements d'état (voir docstring du module)."""
        compte = self.comptes.get(db, compte_id)
        if compte is None:
            return []
        resultat: dict[int, Compte] = {}
        for conversation in self.conversations.lister_du_compte(db, compte.ecole_id, compte_id):
            for membre in self.conversations.membres_resolus(db, conversation.id):
                if membre.id != compte_id:
                    resultat[membre.id] = membre
        return list(resultat.values())

    def entree(self, db: Session, compte_id: int) -> None:
        """Appelé UNE FOIS à l'ouverture du 1er flux SSE d'un compte (pas
        à chaque onglet supplémentaire, voir receiver.py) : prévient ses
        correspondants qu'il vient de passer en ligne."""
        self._publier_etat(db, compte_id, en_ligne=True, derniere_activite_le=None)

    def sortie(self, db: Session, compte_id: int) -> None:
        """Appelé UNE FOIS à la fermeture du DERNIER flux SSE ouvert d'un
        compte (voir receiver.py) : fige sa dernière activité et prévient
        ses correspondants qu'il vient de passer hors ligne."""
        compte = self.comptes.get(db, compte_id)
        if compte is None:
            return
        compte.derniere_activite_le = _utcnow()
        db.commit()
        self._publier_etat(
            db, compte_id, en_ligne=False, derniere_activite_le=compte.derniere_activite_le
        )

    def _publier_etat(
        self, db: Session, compte_id: int, en_ligne: bool, derniere_activite_le: datetime | None
    ) -> None:
        evenement = {
            "type": "etat_connexion",
            "compte_id": compte_id,
            "en_ligne": en_ligne,
            "derniere_activite_le": (
                derniere_activite_le.isoformat() if derniere_activite_le else None
            ),
        }
        for correspondant in self.correspondants(db, compte_id):
            self.evenements.publier(correspondant.id, evenement)
