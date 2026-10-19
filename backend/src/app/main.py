"""Point d'entree unique du backend Contretemps.

Assemble les differents modules metiers (voir backend/README.md et le
decoupage de test-python) sur une seule app FastAPI / un seul service HTTP.
N'appartient a aucun des modules qu'il monte.
"""

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from administrateurs import Administrateurs, AdministrateursReceiver
from acces import Acces
from auth import Auth, AuthReceiver, Invitations, MailsAcces
from assistant import Assistant, AssistantReceiver
from assistant.modifications import Modifications
from bureautique import Bureautique, BureautiqueReceiver
from change import TauxChange, TauxChangeReceiver
from choregraphies import Choregraphies, ChoregraphiesReceiver
from comptes import Comptes, ComptesReceiver, rbac
from cours import CoursReceiver, CoursService
from db import Base, engine
from documents import Documents, DocumentsReceiver, LocalStorage
from documents_contretemps import (
    DOSSIER_DOCUMENTS,
    TAILLE_MAX_MO,
    AnnuaireContretemps,
    MessagerieContretemps,
    NotifieurDocuments,
    SaisonsContretemps,
    membre_appelant,
    recopieur_de_saison,
)
from ecoles import EcoleExport, Ecoles, EcolesReceiver
from eleves import Eleves, ElevesReceiver, ImportExcel, ImportExcelReceiver
from inscriptions import HelloAsso, Inscriptions, InscriptionsReceiver
from inscriptions.fiches import FichesPapier
from inscriptions.stockage import DOSSIER_INSCRIPTIONS
from ressources import Ressources, RessourcesReceiver
from personnalisation.ia import detourage_ia_disponible
from personnalisation.personnalisation import DOSSIER_PERSONNALISATION, Personnalisation
from personnalisation.receiver import PersonnalisationReceiver
from messagerie import Connexions, Conversations, Evenements, Frappe, MessagerieReceiver, Messages
from notifications import Notifications, NotificationsReceiver
from notes_frais import LecteurClaude, NotesDeFrais, NotesDeFraisReceiver, Ports, StockageEnveloppes
from notes_frais_contretemps import (
    AnnuaireContretemps as AnnuaireNotesFrais,
    ClasseurContretemps,
    MessagerContretemps,
    NotifieurContretemps,
    membre_appelant as membre_notes_frais,
)
from presence import Presence, PresenceReceiver
from saisons.gestion import GestionSaisons
from saisons.portee import MiddlewareSaison, SaisonEnLectureSeule
from saisons.receiver import SaisonsReceiver
from profs import Profs, ProfsReceiver
from fusion import Fusion, FusionReceiver
from videos import DOSSIER_VIDEOS_LIVE, Videos, VideosReceiver

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
app = FastAPI(
    title="Contretemps API", lifespan=lifespan, dependencies=[Depends(rbac.session_requise)]
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

# Saisons (Admin > École, spec §2.6) : lister, créer avec duplication,
# éditer la saison courante.
gestion_saisons = GestionSaisons()
saisons_receiver = SaisonsReceiver(client=gestion_saisons, app=app)

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

# Monte les routes de presence (/seances, /cours/{id}/seances, /profs/{id}/heures) - depend de cours.
presence_client = Presence(cours=cours_client)
presence_receiver = PresenceReceiver(client=presence_client, app=app)

# Monte les routes des ecoles (/ecoles, /ecoles/{id}/export) - "export"
# (Admin > Ecole, "Telecharger donnees Ecole") depend de comptes/eleves/
# cours/presence, d'ou la construction ici plutot qu'avec ecoles_client
# plus haut (voir son commentaire).
ecole_export_client = EcoleExport(
    comptes=comptes_client, eleves=eleves_client, cours=cours_client, presence=presence_client
)
ecoles_receiver = EcolesReceiver(
    client=ecoles_client, export=ecole_export_client, comptes=comptes_client, app=app
)

# Monte les routes des choregraphies (/cours/{id}/choregraphies, /choregraphies/...) - depend de cours.
# Module generique (voir videos/models.py) : aucune dependance metier. Monte
# AVANT les choregraphies, qui s'appuient dessus.
videos_client = Videos()
videos_receiver = VideosReceiver(client=videos_client, app=app)

choregraphies_client = Choregraphies(cours=cours_client, videos=videos_client)
choregraphies_receiver = ChoregraphiesReceiver(client=choregraphies_client, app=app)

# Monte les routes des videos (/cours/{id}/videos, /choregraphies/{id}/videos, /videos/...).

# Les fichiers vidéo (un dossier par école, voir videos/stockage.py) ne
# sont plus servis en statique : seulement par /videos/{id}/fichier, avec
# un lien signé à durée limitée (voir securite/liens.py).
DOSSIER_VIDEOS_LIVE.mkdir(parents=True, exist_ok=True)

# Monte les routes des notifications push (/push/..., voir
# notifications/) - independant des autres modules, mais utilise par
# messagerie ci-dessous pour notifier un nouveau message.
notifications_client = Notifications()
notifications_receiver = NotificationsReceiver(client=notifications_client, app=app)

# Monte les routes de messagerie (/conversations, /dm, /messages...) - depend
# de comptes et cours (resolution des membres "cours"). evenements_client
# (flux SSE) instancie plus haut, voir le "lifespan" au-dessus.
conversations_client = Conversations(comptes=comptes_client, cours=cours_client)
messages_client = Messages(conversations=conversations_client)
connexions_client = Connexions(
    comptes=comptes_client, conversations=conversations_client, evenements=evenements_client
)
frappe_client = Frappe()
messagerie_receiver = MessagerieReceiver(
    conversations=conversations_client,
    messages=messages_client,
    evenements=evenements_client,
    connexions=connexions_client,
    frappe=frappe_client,
    notifications=notifications_client,
    app=app,
)

# Monte les routes des inscriptions (/inscriptions/..., voir
# spec/SPEC-inscription.md) - PUBLIQUES (page contretemps-inscription,
# atteignable sans compte), depend de cours (resolution des cours choisis).
helloasso_client = HelloAsso()
inscriptions_client = Inscriptions(cours=cours_client, helloasso=helloasso_client)
# Personnalisation par ecole (spec §2.7, §5.1.1) : adresse web, nom et
# icone de l'appli installee, logo, couleurs, police.
personnalisation_client = Personnalisation(
    ecoles=ecoles_client,
    detourage_ia=detourage_ia_disponible(),
    noter_cout=lambda db, ecole_id, poste, cout, detail: ressources_client.noter_ia(db, ecole_id, poste, cout, detail),
)
personnalisation_receiver = PersonnalisationReceiver(client=personnalisation_client, app=app)

# Justificatifs des notes de frais (module `notes_frais`) : jamais servis
# en statique, seulement par ses routes, après contrôle des droits.
DOSSIER_NOTES_FRAIS = Path(os.environ.get("NOTES_FRAIS_DIR", "./data/notes_frais"))

# "Usage ressources et IA de la saison" (Admin > Ecole) : place sur le
# disque par ecole, et cout des operations d'IA (voir ressources/).
ressources_client = Ressources(
    {
        "videos": ("Vidéos", DOSSIER_VIDEOS_LIVE),
        "documents": ("Documents d'inscription", DOSSIER_INSCRIPTIONS),
        "personnalisation": ("Personnalisation (logo, nom)", DOSSIER_PERSONNALISATION),
        "documents_partages": ("Documents (onglet Docs)", DOSSIER_DOCUMENTS),
        "notes_frais": ("Notes de frais (justificatifs)", DOSSIER_NOTES_FRAIS),
    }
)
ressources_receiver = RessourcesReceiver(client=ressources_client, app=app)

# Onglet Docs : dossiers et fichiers (module `documents`, futur module
# d'AppBase, branché sur Contretemps par documents_contretemps/). Les
# fichiers sont protégés : jamais servis en statique, seulement par ses
# routes, après contrôle des droits.
documents_client = Documents(
    storage=LocalStorage(DOSSIER_DOCUMENTS, TAILLE_MAX_MO * 1024 * 1024),
    directory=AnnuaireContretemps(),
    periods=SaisonsContretemps(),
    mailer=MessagerieContretemps(),
    # Dossier « Financier » de chaque saison : trésoriers seulement, même
    # pas les autres admins (Seb, 17 octobre).
    reserved_folders=(("Financier", "role:tresorier"),),
    notifier=NotifieurDocuments(notifications_client),
)
documents_receiver = DocumentsReceiver(client=documents_client, app=app, current_member=membre_appelant)
# Caddy demande un certificat pour <page>.<école>… : la page doit être en ligne.
personnalisation_client.page_existe = documents_client.apps.page_exists
# Création de saison : « recopier le dossier de la saison précédente ».
gestion_saisons.recopier_documents = recopieur_de_saison(documents_client)

# Assistant de l'onglet Docs (prototype, réservé au Super User) : lit les
# dossiers et fichiers, propose des actions que l'appli exécute après « Faire ».
# Édition Word / Excel / PowerPoint avec OnlyOffice (essai, réservé au
# Super User) : serveur de documents partagé du VPS (voir bureautique/).
def _membre_de(db, compte_id: int, org_id: int):
    from dataclasses import replace as _replace

    from comptes.models import Compte as _Compte
    from saisons.portee import TOUTES_SAISONS

    compte = db.get(_Compte, compte_id, execution_options={TOUTES_SAISONS: True})
    return _replace(membre_appelant(db=db, compte=compte), org_id=org_id)


bureautique_client = Bureautique(documents=documents_client, membre_de=_membre_de)
bureautique_receiver = BureautiqueReceiver(client=bureautique_client, app=app, current_member=membre_appelant)

# Taux dollar -> euro (BCE, une lecture par jour) : les coûts d'IA sont
# affichés en euros (voir change/taux.py).
taux_change_client = TauxChange(fichier=DOSSIER_DOCUMENTS.parent / "taux_change.json")
taux_change_receiver = TauxChangeReceiver(client=taux_change_client, app=app)

assistant_client = Assistant(
    documents=documents_client,
    noter_cout=lambda db, ecole_id, cout, detail: ressources_client.noter_ia(db, ecole_id, "chat_documents", cout, detail),
    cout_saison=lambda db, ecole_id: ressources_client.cout_categorie(db, ecole_id, "chat_documents"),
)
assistant_client.plafond_atteint = ressources_client.plafond_assistant_atteint
assistant_client.modifications = Modifications(
    eleves=eleves_client, comptes=comptes_client, cours=cours_client,
    presence=presence_client, choregraphies=choregraphies_client,
)
assistant_receiver = AssistantReceiver(client=assistant_client, app=app, current_member=membre_appelant)

# Notes de frais (module `notes_frais`, futur module d'AppBase, branché sur
# Contretemps par notes_frais_contretemps/ ; spec/modules/notes-de-frais.md).
notes_frais_client = NotesDeFrais(
    ports=Ports(
        annuaire=AnnuaireNotesFrais(),
        messager=MessagerContretemps(),
        notifieur=NotifieurContretemps(notifications_client),
        lecteur=LecteurClaude(
            noter_cout=lambda db, ecole_id, cout, detail: ressources_client.noter_ia(db, ecole_id, "lecture_ticket", cout, detail),
            plafond_atteint=ressources_client.plafond_assistant_atteint,
        ),
        classeur=ClasseurContretemps(documents_client),
    ),
    stockage=StockageEnveloppes(DOSSIER_NOTES_FRAIS, 20 * 1024 * 1024),
)
notes_frais_receiver = NotesDeFraisReceiver(client=notes_frais_client, app=app, membre_courant=membre_notes_frais)

inscriptions_receiver = InscriptionsReceiver(
    client=inscriptions_client,
    app=app,
    fiches=FichesPapier(
        cours=cours_client,
        eleves=eleves_client,
        noter_cout=lambda db, ecole_id, cout, detail: ressources_client.noter_ia(
            db, ecole_id, "lecture_fiche", cout, detail
        ),
    ),
)


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
