"""Routes REST minimales pour l'écran Profil (voir spec/SPEC.md §5.6) : lire
un compte et lister les profils de sa famille. Les écrans Élèves/Profs ont
leurs propres routes dans leurs modules respectifs, pas ici.
"""

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from db import get_db

from . import rbac, roles
from .comptes import Comptes
from .models import Compte
from .schemas import CompteModification, CompteSortie


class ComptesReceiver:
    def __init__(self, client: Comptes, app: FastAPI) -> None:
        self.client = client
        self.app = app
        self._register_routes()

    def _register_routes(self) -> None:
        self.app.get("/comptes", response_model=list[CompteSortie])(self.lister)
        # Contacts de la messagerie dans toute école (spec/core.md §6.1).
        self.app.get("/super-users", response_model=list[CompteSortie])(self.lister_superusers)
        self.app.get("/comptes/{compte_id}", response_model=CompteSortie)(self.obtenir)
        # Profil admin (email/téléphone/code de récupération) : réservé aux
        # admins de l'école du compte modifié (RBAC, §2.4).
        self.app.put(
            "/comptes/{compte_id}",
            response_model=CompteSortie,
            dependencies=[Depends(self._admin_du_compte)],
        )(self.modifier)
        self.app.get("/comptes/{compte_id}/famille", response_model=list[CompteSortie])(
            self.famille
        )
        # Reprise de session (saisons, §2.6) : la fiche de la même personne
        # dans la saison courante, pour basculer sans reconnexion.
        self.app.get("/comptes/{compte_id}/fiche-courante")(self.fiche_courante)

    def lister(self, ecole_id: int, role: str, db: Session = Depends(get_db)):
        """Utilisé par Admin > Conversations pour proposer les vrais
        comptes admin de l'école (voir AdminGroupes.jsx) — pas encore
        d'écran de gestion multi-admin dédié (spec/SPEC.md §8), donc pas
        de route plus générale pour l'instant."""
        return self.client.list_par_role(db, ecole_id, role)

    def lister_superusers(self, db: Session = Depends(get_db)):
        """Le Super User reste absent des listes de personnes, mais on le
        trouve et on l'ajoute dans les conversations de toute école
        (décision de Seb du 2026-10-18, spec/core.md §6.1). Nom et prénom
        seulement : ni email ni téléphone."""
        return [
            {
                "id": c.id, "ecole_id": None, "famille_id": None, "role": roles.SUPERUSER,
                "roles": [roles.SUPERUSER], "nom": c.nom, "prenom": c.prenom,
                "email": None, "emails": [], "telephone": None,
            }
            for c in self.client.superusers(db)
        ]

    def _admin_du_compte(
        self,
        compte_id: int,
        db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ) -> None:
        compte = self.client.get(db, compte_id)
        rbac.require_admin(appelant, compte.ecole_id if compte else None)

    def obtenir(
        self,
        compte_id: int,
        db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        compte = self.client.get(db, compte_id)
        # Le Superuser est invisible (§2.5) : son compte n'est lisible que
        # par lui-même (reprise de session). Pour tout autre appelant, il
        # n'existe pas.
        if compte is not None and roles.is_superuser(compte) and (appelant is None or appelant.id != compte.id):
            compte = None
        if compte is None:
            raise HTTPException(status_code=404, detail="Compte introuvable")
        return compte

    def modifier(self, compte_id: int, donnees: CompteModification, db: Session = Depends(get_db)):
        """Profil admin (voir ProfilScreen.jsx) : crayon à côté de
        l'email/du code de récupération."""
        try:
            compte = self.client.update(db, compte_id, **donnees.model_dump(exclude_unset=True))
        except ValueError as erreur:
            raise HTTPException(status_code=422, detail=str(erreur)) from erreur
        if compte is None:
            raise HTTPException(status_code=404, detail="Compte introuvable")
        return compte

    def fiche_courante(self, compte_id: int, db: Session = Depends(get_db)):
        """{"compte_id": ...} ; 404 si la personne n'est pas dans la saison
        courante (fiche d'une ancienne saison non reprise, ou inconnue).
        Même niveau de confiance que l'en-tête X-Compte-Id (§8) : ne
        révèle qu'un numéro de fiche."""
        compte = self.client.get_toutes_saisons(db, compte_id)
        nouvelle = self.client.fiche_courante(db, compte) if compte is not None else None
        if nouvelle is None or roles.is_superuser(nouvelle):
            raise HTTPException(status_code=404, detail="Pas inscrit(e) pour la saison en cours")
        return {"compte_id": nouvelle.id}

    def famille(
        self,
        compte_id: int,
        db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        """Les profils du sélecteur (§2.1, §4) : ceux de l'email connecté."""
        rbac.meme_personne(appelant, compte_id, db)
        compte = self.client.get(db, compte_id)
        if compte is None:
            return []
        # Sans session (tests où elle est neutralisée) : tous les emails de
        # la fiche.
        email = getattr(appelant, "email_connecte", None)
        return self.client.profils_de_l_email(db, compte, [email] if email else compte.emails)
