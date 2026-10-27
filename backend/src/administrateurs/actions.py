"""Actions des rôles ouvertes à l'assistant (spec/modules/assistant-ia.md §3) :
nommer un administrateur, changer les rôles Administrateur, Trésorier et
Administrateur principal, et les fonctions au bureau (spec/core.md §6.4). Comme le tableau des administrateurs d'Admin >
École : réservé aux administrateurs principaux (et au Super User), jamais
sur sa propre ligne sauf la case Trésorier et le bureau ; les règles des rôles restent
celles de Comptes.ajouter_role / retirer_role.
"""

from __future__ import annotations

from assistant.actions import Action
from assistant.modifications import Ligne, Refus
from comptes import Compte, rbac, roles
from groups import board
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .administrateurs import Administrateurs, _promu
from .schemas import BureauFunction, ordered_functions

BUREAU_LABELS = {
    "president": "président·e", "vice_president": "vice-président·e", "secretary": "secrétaire", "treasurer": "trésorier·e",
}


class ChangeRoles(BaseModel):
    person_id: int = Field(description="Numéro de la personne (lu avec lister_personnes).")
    admin: bool | None = Field(default=None, description="Administrateur : true, false, ou null pour ne pas changer.")
    treasurer: bool | None = Field(default=None, description="Trésorier (exige d'être administrateur), ou null.")
    main_admin: bool | None = Field(default=None, description="Administrateur principal (exige d'être administrateur), ou null.")
    bureau_functions: list[BureauFunction] | None = Field(
        default=None,
        description="Fonctions au bureau (exige d'être administrateur), la liste complète qui remplace l'ancienne, "
        "ou null pour ne pas changer. Ce sont des titres, sans droit : la fonction treasurer n'ouvre pas le Financier.",
    )


class NewAdmin(BaseModel):
    last_name: str = Field(min_length=1, max_length=100, description="Nom.")
    first_name: str = Field(min_length=1, max_length=100, description="Prénom.")
    email: str | None = Field(default=None, description="Email, pour l'invitation.")
    main_admin: bool = Field(default=False, description="Administrateur principal.")


def actions(client: Administrateurs) -> list[Action]:
    def prepare_roles(db: Session, compte, org_id: int, p: ChangeRoles) -> Ligne:
        rbac.require_owner(compte, org_id)
        cible = db.get(Compte, p.person_id)
        if cible is None or cible.ecole_id != org_id:
            raise Refus("personne introuvable dans cette école")
        if cible.id == compte.id and (p.admin is not None or p.main_admin is not None):
            raise Refus("on ne change pas ses propres rôles, sauf la case Trésorier et le bureau")
        avant = {"admin": roles.is_admin(cible), "treasurer": roles.is_tresorier(cible), "main_admin": roles.is_owner(cible)}
        apres = {k: v if v is not None else avant[k] for k, v in p.model_dump(exclude={"person_id", "bureau_functions"}).items()}
        if not apres["admin"]:
            apres["treasurer"] = apres["main_admin"] = False  # tous deux exigent d'être administrateur
        if apres["admin"] and not avant["admin"] and not _promu(cible):
            raise Refus("seul un élève ou un professeur peut être nommé administrateur ; sinon, créer un administrateur")
        noms = {"admin": "administrateur", "treasurer": "trésorier", "main_admin": "administrateur principal"}
        changes = [f"devient {noms[k]}" if apres[k] else f"n'est plus {noms[k]}" for k in noms if apres[k] != avant[k]]
        bureau = None if p.bureau_functions is None else ordered_functions(p.bureau_functions)
        if bureau is not None and bureau != board.functions_of(db, cible):
            if not apres["admin"]:
                raise Refus("seul un administrateur a une fonction au bureau")
            libelles = ", ".join(BUREAU_LABELS[f] for f in bureau)
            changes.append(f"bureau : {libelles}" if bureau else "ne fait plus partie du bureau")
        else:
            bureau = None
        if not changes:
            raise Refus("rien ne change")
        nom = f"{cible.prenom} {cible.nom}".strip()
        if avant["admin"] and not apres["admin"] and not _promu(cible):
            changes.append("son compte est supprimé (il n'était qu'administrateur)")
        cible_id, par_superuser = cible.id, roles.is_superuser(compte)

        def faire(db: Session) -> None:
            c = db.get(Compte, cible_id)
            if apres["admin"] and not avant["admin"]:
                client.promouvoir(db, org_id, cible_id, owner=apres["main_admin"])
                if apres["treasurer"] or bureau is not None:
                    client.modifier(db, c, champs={}, owner=None, tresorier=apres["treasurer"] or None,
                                    bureau_functions=bureau)
            elif avant["admin"] and not apres["admin"]:
                client.supprimer(db, c, par_superuser=par_superuser)
            else:
                client.modifier(
                    db, c, champs={}, owner=apres["main_admin"], tresorier=apres["treasurer"],
                    bureau_functions=bureau, par_superuser=par_superuser,
                )

        return Ligne(f"{nom} : {', '.join(changes)}", faire)

    def prepare_new_admin(db: Session, compte, org_id: int, p: NewAdmin) -> Ligne:
        rbac.require_owner(compte, org_id)
        nom = f"{p.first_name} {p.last_name}".strip()
        role = "administrateur principal" if p.main_admin else "administrateur"
        return Ligne(
            f"Créer l'{role} {nom}" + (f" ({p.email})" if p.email else ""),
            lambda db: client.creer(
                db, org_id, nom=p.last_name.strip(), prenom=p.first_name.strip(), email=p.email, owner=p.main_admin
            ),
        )

    return [
        Action("change_roles", "Rôles", "Nomme ou retire un administrateur, un trésorier (accès au Financier) ou un "
               "administrateur principal parmi les personnes de l'école, et change ses fonctions au bureau "
               "(président, secrétaire…). Réservé aux administrateurs principaux.", ChangeRoles, prepare_roles),
        Action("create_admin", "Rôles", "Crée une personne qui n'est qu'administrateur (ni élève ni professeur), "
               "par exemple un membre du bureau. Réservé aux administrateurs principaux.", NewAdmin, prepare_new_admin),
    ]
