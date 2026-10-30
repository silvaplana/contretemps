"""Point d'entree unique du backend Contretemps.

Assemble les differents modules metiers (voir backend/README.md et le
decoupage de test-python) sur une seule app FastAPI / un seul service HTTP.
N'appartient a aucun des modules qu'il monte.
"""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from administrateurs import Administrateurs, AdministrateursReceiver
from acces import Acces
from auth import Auth, AuthReceiver, Invitations, MailsAcces
from assistant.actions import Actions
from assistant.guide import guide_action
from registry import guide_file
from change import TauxChange, TauxChangeReceiver
from comptes import Comptes, ComptesReceiver, rbac
from cours import CoursReceiver, CoursService
from administrateurs.actions import actions as actions_administrateurs
from cours.actions import actions as actions_cours
from ecoles.actions import actions as actions_ecoles
from eleves.actions import actions as actions_eleves
from db import Base, engine
from documents_contretemps import DOSSIER_DOCUMENTS, membre_appelant
from ecoles import EcoleExport, Ecoles, EcolesReceiver
from eleves import Eleves, ElevesReceiver, ImportExcel, ImportExcelReceiver
from inscriptions.stockage import DOSSIER_INSCRIPTIONS
from ressources import Ressources, RessourcesReceiver
from personnalisation.ia import detourage_ia_disponible
from personnalisation.personnalisation import DOSSIER_PERSONNALISATION, Personnalisation
from personnalisation.receiver import PersonnalisationReceiver
from messagerie import Evenements
from app.messagerie_stockage import DOSSIER_MESSAGERIE, pieces_jointes
from app.modules import MODULES
from notifications import Notifications, NotificationsReceiver
from notes_frais_contretemps.module import DOSSIER_NOTES_FRAIS
from profs.actions import actions as actions_profs
import registry
from registry.activation import disabled as modules_eteints
from registry.activation import route_enabled
from registry.receiver import ModulesReceiver
from saisons.gestion import GestionSaisons
from saisons.portee import MiddlewareSaison, SaisonEnLectureSeule
from profs import Profs, ProfsReceiver
from fusion import Fusion, FusionReceiver
from members.receiver import DOSSIER_MEMBRES, MembersReceiver
from plans.receiver import PlansReceiver
from plans.rules import RuleReader
from videos import DOSSIER_VIDEOS_LIVE

load_dotenv()  # charge backend/.env si present

# Flux SSE de la messagerie (voir messagerie/evenements.py) - instancie
# ici, avant l'app, pour que le "lifespan" ci-dessous puisse le capturer
# a son demarrage (il a besoin de la VRAIE boucle asyncio qui sert les
# requetes, connue seulement une fois uvicorn effectivement lance).
evenements_client = Evenements()


@asynccontextmanager
async def lifespan(app: FastAPI):
    evenements_client.demarrer(asyncio.get_running_loop())
    yield


# Session obligatoire sur TOUTES les routes (spec §2.2), sauf la courte
# liste des routes publiques (voir comptes/rbac.py : ROUTES_PUBLIQUES).
# Puis les routes d'un module éteint dans l'école de l'appelant répondent
# « introuvable » (spec/core.md §9 bis.3, registry/activation.py).
app = FastAPI(
    title="Contretemps API",
    lifespan=lifespan,
    dependencies=[Depends(rbac.session_requise), Depends(route_enabled)],
)
# Saison affichée demandée par le navigateur (en-tête X-Saison-Id), voir
# saisons/portee.py.
app.add_middleware(MiddlewareSaison)


@app.exception_handler(SaisonEnLectureSeule)
async def _saison_en_lecture_seule(request: Request, erreur: SaisonEnLectureSeule):
    # Toute écriture dans une ancienne saison (spec §2.6), où qu'elle soit
    # tentée : refusée par saisons/portee.py, jamais par chaque route.
    return JSONResponse(status_code=403, content={"detail": erreur.message})


app.add_middleware(
    # Autorise le frontend React (Vite, servi sur un autre port en dev) a
    # appeler l'API. A restreindre a une origine precise avant mise en prod.
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    # Jeton de session prolongé (voir comptes/rbac.py), que l'appli doit
    # pouvoir lire dans la réponse.
    expose_headers=[rbac.ENTETE_JETON_RENOUVELE],
)

# Cree les tables si elles n'existent pas encore (pratique en dev/SQLite ;
# en prod, voir plutot Alembic - backend/alembic/ - pour les migrations
# reelles). Chaque module importe pour son cote (ci-dessous) enregistre ses
# tables sur Base.metadata au moment de l'import.
Base.metadata.create_all(bind=engine)

# Plusieurs emails par fiche (spec §6.3) : reprend les anciennes adresses
# si la migration n'a pas encore été lancée.
from comptes.reprise_emails import reprendre_anciens_emails  # noqa: E402

reprendre_anciens_emails(engine)

# Plafond mensuel de l'assistant : même filet, si la migration manque.
from ecoles.colonne_plafond import ajouter_colonne_plafond  # noqa: E402

ajouter_colonne_plafond(engine)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# Service ecoles (pas encore ses routes, voir plus bas) - instancie tot
# car auth_client en a besoin juste apres. EcolesReceiver, lui, attend
# d'avoir comptes/eleves/cours/presence pour la route d'export (voir
# ecoles/excel_export.py) - construit plus bas, une fois ces 4 pretes.
ecoles_client = Ecoles()

# Monte les routes des comptes (/comptes) - socle reutilise par auth
# ci-dessous, et plus tard par eleves/profs.
comptes_client = Comptes()
comptes_receiver = ComptesReceiver(client=comptes_client, app=app)

# Tableau des administrateurs (Admin > École, spec §2.4) : lister, créer,
# modifier, supprimer un admin — réservé aux Owners pour l'écriture.
administrateurs_client = Administrateurs(comptes=comptes_client)
administrateurs_receiver = AdministrateursReceiver(client=administrateurs_client, app=app)
# Champs des membres (spec/core.md §4.3) : la fiche et ses réponses.
members_receiver = MembersReceiver(app=app)
# Tarifs de la saison (spec/core.md §9) : formules, options et codes promo,
# règles en français comprises par l'assistant (coût noté dans Ressources).
plans_receiver = PlansReceiver(
    app=app,
    reader=RuleReader(
        noter_cout=lambda db, ecole_id, cout, detail: ressources_client.noter_ia(db, ecole_id, "regle_tarif", cout, detail),
        plafond_atteint=lambda db, ecole_id: ressources_client.plafond_assistant_atteint(db, ecole_id),
    ),
)

# Saisons (spec §2.6) : la création avec duplication, reliée plus bas aux
# documents. Ses routes sont celles du module Saisons (saisons/module.py).
gestion_saisons = GestionSaisons()

# Monte les routes de connexion (/auth/...) - depend de ecoles et comptes.
acces_client = Acces()
auth_client = Auth(comptes=comptes_client, acces=acces_client)
invitations_client = Invitations(acces=acces_client, mails=MailsAcces())
auth_receiver = AuthReceiver(client=auth_client, invitations=invitations_client, app=app)

# Monte les routes des cours (/cours) - depend de comptes (professeurs/eleves)
# et evenements_client (SSE : sélecteur de cours tenu à jour en direct,
# voir cours/receiver.py: _publier_cours_maj — demande utilisateur du
# 2026-09-19).
cours_client = CoursService()
cours_receiver = CoursReceiver(
    client=cours_client, app=app, evenements=evenements_client, comptes=comptes_client
)

# Monte les routes des eleves (/eleves, /contacts) - depend de comptes.
eleves_client = Eleves(comptes=comptes_client)
eleves_receiver = ElevesReceiver(client=eleves_client, comptes=comptes_client, app=app)

# Monte les routes de l'import Excel des eleves (/eleves/import/...) -
# depend de eleves (reutilise ses primitives CRUD) et cours.
import_excel_client = ImportExcel(eleves=eleves_client, cours=cours_client)
import_excel_receiver = ImportExcelReceiver(client=import_excel_client, app=app)

# Monte les routes des profs (/profs) - depend de comptes et cours.
profs_client = Profs(comptes=comptes_client, cours=cours_client)
profs_receiver = ProfsReceiver(client=profs_client, app=app)
# Une personne = une fiche (spec/core.md §4) : « Fusionner avec… ».
fusion_receiver = FusionReceiver(client=Fusion(comptes_client), app=app)

# Monte les routes des notifications push (/push/..., voir
# notifications/) - independant des autres modules, mais utilise par
# messagerie (nouveau message), Docs et notes de frais pour notifier.
notifications_client = Notifications()
notifications_receiver = NotificationsReceiver(client=notifications_client, app=app)

# Personnalisation par ecole (spec §2.7, §5.1.1) : adresse web, nom et
# icone de l'appli installee, logo, couleurs, police.
personnalisation_client = Personnalisation(
    ecoles=ecoles_client,
    detourage_ia=detourage_ia_disponible(),
    noter_cout=lambda db, ecole_id, poste, cout, detail: ressources_client.noter_ia(db, ecole_id, poste, cout, detail),
)
personnalisation_receiver = PersonnalisationReceiver(client=personnalisation_client, app=app)

# "Usage ressources et IA de la saison" (Admin > Ecole) : place sur le
# disque par ecole, et cout des operations d'IA (voir ressources/).
ressources_client = Ressources(
    {
        "videos": ("Vidéos", DOSSIER_VIDEOS_LIVE),
        "documents": ("Documents d'inscription", DOSSIER_INSCRIPTIONS),
        "personnalisation": ("Personnalisation (logo, nom)", DOSSIER_PERSONNALISATION),
        "documents_partages": ("Documents (onglet Docs)", DOSSIER_DOCUMENTS),
        "notes_frais": ("Notes de frais (justificatifs)", DOSSIER_NOTES_FRAIS),
        "messagerie": ("Messagerie (photos, vidéos et fichiers)", DOSSIER_MESSAGERIE),
        "membres": ("Fichiers des membres (champs de la fiche)", DOSSIER_MEMBRES),
    }
)
ressources_receiver = RessourcesReceiver(client=ressources_client, app=app)

# Taux dollar -> euro (BCE, une lecture par jour) : les coûts d'IA sont
# affichés en euros (voir change/taux.py).
taux_change_client = TauxChange(fichier=DOSSIER_DOCUMENTS.parent / "taux_change.json")
taux_change_receiver = TauxChangeReceiver(client=taux_change_client, app=app)

# Modules de l'appli (spec/core.md §9 bis) : la liste est dans
# app/modules.py, chacun monte ses routes depuis son module.py. `core` porte
# ce qu'ils trouvent en arrivant (fiches, cours, notifications, coûts…) et ce
# que chacun y range pour les suivants (ex. core.documents_client).
core = SimpleNamespace(
    comptes_client=comptes_client,
    cours_client=cours_client,
    eleves_client=eleves_client,
    evenements_client=evenements_client,
    notifications_client=notifications_client,
    ressources_client=ressources_client,
    personnalisation_client=personnalisation_client,
    gestion_saisons=gestion_saisons,
    membre_appelant=membre_appelant,
    message_attachments=pieces_jointes(),
)
registry.mount_all(app, MODULES, core)

presence_client = core.presence_client
videos_client = core.videos_client
choregraphies_client = core.choregraphies_client
messagerie_receiver = core.messagerie_receiver
inscriptions_client = core.inscriptions_client
inscriptions_receiver = core.inscriptions_receiver
documents_client = core.documents_client
assistant_client = core.assistant_client
notes_frais_client = core.notes_frais_client
finances_client = core.finances_client
finances_reports = core.finances_reports
finances_assemblies = core.finances_assemblies
finances_forecasts = core.finances_forecasts

# Monte les routes des ecoles (/ecoles, /ecoles/{id}/export) - "export"
# (Admin > Ecole, "Telecharger donnees Ecole") depend de comptes/eleves/
# cours/presence, d'ou la construction ici, une fois les modules montés.
ecole_export_client = EcoleExport(
    comptes=comptes_client, eleves=eleves_client, cours=cours_client, presence=presence_client
)
ecoles_receiver = EcolesReceiver(
    client=ecoles_client, export=ecole_export_client, comptes=comptes_client, app=app
)

# Modules allumés ou éteints par école (spec/core.md §9 bis.3) : lus par
# l'appli pour ses onglets, changés par le Super User dans Supervision.
modules_receiver = ModulesReceiver(modules=MODULES, app=app)

# Actions ouvertes à l'assistant (spec/modules/assistant-ia.md §3) : celles
# du socle de Contretemps, puis celles que chaque module déclare dans son
# module.py (spec/core.md §9 bis), dans l'ordre de app/modules.py. Celles
# d'un module éteint dans l'école sont cachées.
actions_des_modules = registry.actions(MODULES, core)
# Plan des écrans du socle (barre du bas, Admin, Profil, Supervision) pour le
# guide de l'assistant, à côté de celui de chaque module.
core_guide = guide_file(__file__)
assistant_client.actions = Actions(
    [
        *actions_ecoles(ecoles_client),
        *actions_administrateurs(administrateurs_client),
        *actions_eleves(eleves_client),
        *actions_profs(profs_client),
        *actions_cours(cours_receiver),
        *(action for liste in actions_des_modules.values() for action in liste),
        guide_action(MODULES, modules_eteints, core_guide),
    ],
    hidden=lambda db, org_id: {
        action.name for cle in modules_eteints(db, org_id) for action in actions_des_modules.get(cle, [])
    },
)


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
