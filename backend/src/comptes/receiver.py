"""Routes REST minimales pour l'écran Profil (voir spec/SPEC.md §5.6) : lire
un compte et lister les profils de sa famille. Les écrans Élèves/Profs ont
leurs propres routes dans leurs modules respectifs, pas ici.
"""

from fastapi import Depends, FastAPI, Header, HTTPException
from sqlalchemy.orm import Session

from db import get_db
from securite import jetons

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
        authorization: str | None = Header(default=None),
    ):
        compte = self.client.get(db, compte_id)
        jeton = jetons.depuis_entete(authorization)
        a_son_jeton = jeton is not None and compte is not None and jeton.compte_id == compte.id
        # Le Superuser est invisible (§2.5) : son compte n'est lisible que
        # par lui-même, avec son jeton (reprise de session). Pour tout autre
        # appelant, il n'existe pas.
        if compte is not None and roles.is_superuser(compte) and not a_son_jeton:
            compte = None
        if compte is None:
            raise HTTPException(status_code=404, detail="Compte introuvable")
        # Élève promu admin (§2.4) : rôles admin/owner présentés seulement
        # si SON jeton "admin" accompagne la requête (reprise de session
        # après une connexion par le code admin) — sinon, un élève.
        if roles.admin_sous_condition(compte):
            sortie = CompteSortie.model_validate(compte)
            admin_actif = a_son_jeton and jeton.portee == jetons.ADMIN
            sortie.roles = roles.roles_effectifs(compte, admin_actif)
            sortie.role = roles.role_principal(sortie.roles)
            return sortie
        return compte

    def modifier(self, compte_id: int, donnees: CompteModification, db: Session = Depends(get_db)):
        """Profil admin (voir ProfilScreen.jsx) : crayon à côté de
        l'email/du code de récupération."""
        compte = self.client.update(db, compte_id, **donnees.model_dump(exclude_unset=True))
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

    def famille(self, compte_id: int, db: Session = Depends(get_db)):
        # Un élève promu admin figure en élève dans le sélecteur familial :
        # basculer vers lui sans code n'active pas ses droits (§2.4).
        membres = []
        for membre in self.client.membres_de_la_famille(db, compte_id):
            if roles.admin_sous_condition(membre):
                sortie = CompteSortie.model_validate(membre)
                sortie.roles = roles.roles_effectifs(membre, admin_actif=False)
                sortie.role = roles.role_principal(sortie.roles)
                membre = sortie
            membres.append(membre)
        return membres
