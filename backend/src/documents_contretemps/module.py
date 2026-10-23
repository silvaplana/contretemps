"""Déclaration du module Documents pour Contretemps (spec/core.md §9 bis) :
le module `documents` reste sans dépendance à l'appli, c'est ici qu'il est
relié aux fiches, aux saisons et à la messagerie de Contretemps. Comprend
l'édition Word / Excel / PowerPoint (OnlyOffice, `bureautique`)."""

from dataclasses import replace

from bureautique import Bureautique, BureautiqueReceiver
from comptes.models import Compte
from documents import Documents, DocumentsReceiver, LocalStorage
from documents.attendance_photo import AttendanceReader
from registry import Module
from saisons.portee import TOUTES_SAISONS

from .actions import actions
from . import lien_fichier
from .adapter import (
    DOSSIER_DOCUMENTS,
    TAILLE_MAX_MO,
    AnnuaireContretemps,
    AssociationContretemps,
    MessagerieContretemps,
    NotifieurDocuments,
    SaisonsContretemps,
    membre_appelant,
    recopieur_de_saison,
)


def membre_de(db, compte_id: int, org_id: int):
    """La fiche `compte_id` vue comme membre de l'organisation `org_id`."""
    compte = db.get(Compte, compte_id, execution_options={TOUTES_SAISONS: True})
    return replace(membre_appelant(db=db, compte=compte), org_id=org_id)


def mount(app, core) -> None:
    ressources = core.ressources_client
    # Les fichiers sont protégés : jamais servis en statique, seulement par
    # les routes du module, après contrôle des droits.
    documents_client = Documents(
        storage=LocalStorage(DOSSIER_DOCUMENTS, TAILLE_MAX_MO * 1024 * 1024),
        directory=AnnuaireContretemps(),
        periods=SaisonsContretemps(),
        mailer=MessagerieContretemps(),
        # Dossier « Financier » de chaque saison : trésoriers seulement, même
        # pas les autres admins (Seb, 17 octobre).
        reserved_folders=(("Financier", "role:tresorier"),),
        notifier=NotifieurDocuments(core.notifications_client),
        # Convoquer une première AG : tous les membres de la saison.
        members=(("group", "role:eleve"), ("group", "role:professeur"), ("group", "role:admin")),
        # Feuille d'émargement à signer : les membres payants, c'est-à-dire les élèves.
        voters=(("group", "role:eleve"),),
        attendance_reader=AttendanceReader(
            note_cost=lambda db, ecole_id, cout, detail: ressources.noter_ia(db, ecole_id, "liste_presents", cout, detail),
        ),
        association=AssociationContretemps(),
    )
    core.documents_client = documents_client
    DocumentsReceiver(client=documents_client, app=app, current_member=membre_appelant)
    # PDF ouvert dans la visionneuse du téléphone, par un lien signé.
    lien_fichier.brancher(app, documents_client, membre_appelant)
    # Caddy demande un certificat pour <page>.<école>… : la page doit être en ligne.
    core.personnalisation_client.page_existe = documents_client.apps.page_exists
    # Création de saison : « recopier le dossier de la saison précédente ».
    core.gestion_saisons.recopier_documents = recopieur_de_saison(documents_client)

    # Édition Word / Excel / PowerPoint avec OnlyOffice (essai, réservé au
    # Super User) : serveur de documents partagé du VPS (voir bureautique/).
    BureautiqueReceiver(client=Bureautique(documents=documents_client, membre_de=membre_de), app=app, current_member=membre_appelant)


MODULE = Module(
    key="documents", label="Documents", mount=mount,
    actions=lambda core: actions(core.documents_client),
)
