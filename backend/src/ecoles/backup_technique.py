"""Sauvegarde/restauration TECHNIQUE complète d'une école ("Sauvegarder
École" / "Importer sauvegarde", Admin > École) — pensée pour repeupler une
appli Contretemps vide de cette école en cas de crash, PAS pour être lue/
modifiée à la main (contrairement à l'export humain, voir excel_export.py).

Un onglet par table, en-têtes = noms de colonnes EXACTS (anglais/français
tels qu'en base) plutôt que des libellés jolis — pour un aller-retour
export -> réimport sans ambiguïté. IDs internes conservés tels quels (les
lignes se référencent entre elles par id, ex. un message référence sa
conversation) — voir `restaurer()` pour pourquoi c'est sûr même dans une
base PARTAGÉE entre plusieurs écoles.

⚠️ Hors périmètre (décisions prises avec l'utilisateur, voir conversation) :
- Fichiers vidéo/photos eux-mêmes : seules leurs métadonnées (nom, lien de
  fichier, durée...) sont sauvegardées, jamais le contenu binaire — ils
  restent dans leur propre stockage sur le serveur, en dehors de ce
  mécanisme.
- Le module `inscriptions` (parcours d'inscription en ligne : dossiers en
  cours, paiement HelloAsso...) : cycle de vie et modèle de sécurité à
  part (tokens publics), non couvert ici. Ni sauvegardé, ni vidé par
  `vider()`.
"""

from __future__ import annotations

import datetime as dt
import io
import json
from dataclasses import dataclass
from typing import Any, Callable

from choregraphies.models import Choregraphie, choregraphies_eleves, choregraphies_videos
from comptes import roles
from comptes.models import Compte, EmailCompte, Famille, RoleCompte, separer_emails
from comptes.reprise_payeurs import reprendre_payeurs
from cours.models import Cours, CoursHoraireSupplementaire, cours_professeurs
from eleves.models import ContactEleve, ProfilEleve
from groups import Group, GroupMember, courses, rights, teachers
from members import MemberColumn, MemberField, MemberValue
from members.fields import known
from messagerie.models import Conversation, ConversationMembre, Message, MessageDelivery
from openpyxl import Workbook, load_workbook
from presence.models import PresenceEleve, PresenceProf, SeancePresence
from saisons import Saison, saison_courante_id
from saisons.portee import toutes_saisons
from sqlalchemy import JSON, Table, delete, insert, select, text, update
from sqlalchemy.orm import Session
from ressources.models import ConsommationIA
from videos.models import Video

from .models import Ecole

COLONNES_ECOLE = [
    "id",
    "nom",
    "code_postal",
    "created_at",
]

# Toutes les saisons de l'école (spec §2.6) : une sauvegarde technique couvre
# l'école entière, anciennes saisons comprises.
COLONNES_SAISON = ["id", "ecole_id", "nom", "date_debut", "date_fin", "created_at"]


@dataclass
class _Table:
    """Une table à sauvegarder/restaurer — dans l'ordre PARENT -> ENFANT
    (voir TABLES plus bas) : `vider()` le parcourt à l'envers (enfants
    d'abord, pour ne jamais casser une contrainte de clé étrangère),
    `restaurer()` dans l'ordre (parents d'abord)."""

    feuille: str
    objet: type | Table  # classe ORM (Compte, Cours...) ou Table brute (join)
    colonnes: list[str]
    # Filtre "appartient à cette école" — chaque table s'y prend
    # différemment (colonne directe, ou jointure via cours/conversation/
    # séance...), voir chaque entrée de TABLES ci-dessous.
    lignes_ecole: Callable[[Session, int], list[Any]]
    # Colonne portant l'ecole_id, si directe sur cette table (voir
    # `restaurer()` : forcée à l'école CIBLE, jamais reprise telle quelle
    # du fichier — un admin peut restaurer un fichier dont les ids
    # internes datent d'avant un redéploiement, voir sa docstring).
    colonne_ecole_id: str | None = None


def _sous_requete_cours_ecole(ecole_id: int):
    return select(Cours.id).where(Cours.ecole_id == ecole_id)


def _sous_requete_comptes_ecole(ecole_id: int):
    return select(Compte.id).where(Compte.ecole_id == ecole_id)


def _sous_requete_conversations_ecole(ecole_id: int):
    return select(Conversation.id).where(Conversation.ecole_id == ecole_id)


def _sous_requete_seances_ecole(ecole_id: int):
    return select(SeancePresence.id).where(SeancePresence.cours_id.in_(_sous_requete_cours_ecole(ecole_id)))


def _sous_requete_choregraphies_ecole(ecole_id: int):
    return select(Choregraphie.id).where(Choregraphie.cours_id.in_(_sous_requete_cours_ecole(ecole_id)))


def _sous_requete_messages_ecole(ecole_id: int):
    return select(Message.id).where(Message.conversation_id.in_(_sous_requete_conversations_ecole(ecole_id)))


# --- Ordre PARENT -> ENFANT (voir _Table ci-dessus) ---
#
# comptes/famille en tête (après cours, qui n'en dépend pas) : cours_id
# et conversation_id/seance_id en dépendent tous en cascade. `famille`
# doit précéder `compte` (FK famille_id) mais un compte peut aussi être
# seul dans sa famille — pas de souci d'ordre entre les deux tant que
# famille passe avant compte.
def _construire_tables() -> list[_Table]:
    return [
        _Table(
            "Familles",
            Famille,
            ["id", "ecole_id", "saison_id", "created_at"],
            lambda db, eid: list(db.scalars(select(Famille).where(Famille.ecole_id == eid))),
            colonne_ecole_id="ecole_id",
        ),
        _Table(
            "Comptes",
            Compte,
            [
                "id", "ecole_id", "famille_id", "saison_id", "compte_precedent_id", "nom", "prenom",
                "telephone", "payer_email", "created_at",
            ],
            lambda db, eid: list(db.scalars(select(Compte).where(Compte.ecole_id == eid))),
            colonne_ecole_id="ecole_id",
        ),
        # Rôles cumulables (§6.3bis), depuis le 2026-09-21. Une sauvegarde
        # plus ancienne n'a pas cet onglet mais une colonne "role" dans
        # "Comptes" : voir `restaurer()`, qui sait relire les deux formats.
        _Table(
            "RolesComptes",
            RoleCompte,
            ["compte_id", "role", "created_at"],
            lambda db, eid: list(
                db.scalars(select(RoleCompte).where(RoleCompte.compte_id.in_(_sous_requete_comptes_ecole(eid))))
            ),
        ),
        # Emails des fiches (plusieurs par fiche, §2.1), depuis le
        # 2026-10-16. Une sauvegarde plus ancienne a une colonne "email"
        # dans "Comptes" : voir `restaurer()`.
        _Table(
            "EmailsComptes",
            EmailCompte,
            ["id", "compte_id", "email", "created_at"],
            lambda db, eid: list(
                db.scalars(select(EmailCompte).where(EmailCompte.compte_id.in_(_sous_requete_comptes_ecole(eid))))
            ),
        ),
        # Groupes du core (spec/core.md §5), depuis le 2026-10-27 : le bureau.
        # Parents avant sous-groupes (ordre des ids).
        _Table(
            "Groupes",
            Group,
            ["id", "org_id", "season_id", "parent_id", "key", "name", "created_at"],
            lambda db, eid: list(db.scalars(select(Group).where(Group.org_id == eid).order_by(Group.id))),
            colonne_ecole_id="org_id",
        ),
        _Table(
            "MembresGroupes",
            GroupMember,
            ["group_id", "member_id", "created_at"],
            lambda db, eid: list(
                db.scalars(select(GroupMember).where(GroupMember.member_id.in_(_sous_requete_comptes_ecole(eid))))
            ),
        ),
        # Champs des membres (spec/core.md §4.3), depuis le 2026-10-27.
        _Table(
            "ChampsMembres",
            MemberField,
            [
                "id", "org_id", "season_id", "label", "required", "format", "choices", "group_id", "multiple",
                "position", "member_sees", "member_edits", "others_see", "for_group_id", "key", "removed_at",
                "created_at",
            ],
            lambda db, eid: list(db.scalars(select(MemberField).where(MemberField.org_id == eid))),
            colonne_ecole_id="org_id",
        ),
        _Table(
            "ColonnesMembres",
            MemberColumn,
            ["org_id", "season_id", "key", "shown", "position"],
            lambda db, eid: list(db.scalars(select(MemberColumn).where(MemberColumn.org_id == eid))),
            colonne_ecole_id="org_id",
        ),
        _Table(
            "ReponsesMembres",
            MemberValue,
            ["member_id", "field_id", "value", "updated_at"],
            lambda db, eid: list(
                db.scalars(select(MemberValue).where(MemberValue.member_id.in_(_sous_requete_comptes_ecole(eid))))
            ),
        ),
        _Table(
            "ProfilsEleves",
            ProfilEleve,
            [
                "compte_id", "date_naissance", "adresse", "allergies", "traitement_medical",
                "informations_importantes", "statut_paiement", "montant_total_annee",
                "montant_paye", "commentaire_admin",
            ],
            lambda db, eid: list(
                db.scalars(select(ProfilEleve).where(ProfilEleve.compte_id.in_(_sous_requete_comptes_ecole(eid))))
            ),
        ),
        _Table(
            "ContactsEleves",
            ContactEleve,
            ["id", "eleve_id", "nom", "prenom", "lien", "telephone", "email"],
            lambda db, eid: list(
                db.scalars(select(ContactEleve).where(ContactEleve.eleve_id.in_(_sous_requete_comptes_ecole(eid))))
            ),
        ),
        _Table(
            "Cours",
            Cours,
            ["id", "ecole_id", "saison_id", "nom", "jour", "heure_debut", "heure_fin", "salle", "descriptif", "ordre", "group_id"],
            lambda db, eid: list(db.scalars(select(Cours).where(Cours.ecole_id == eid))),
            colonne_ecole_id="ecole_id",
        ),
        _Table(
            "CoursHorairesSup",
            CoursHoraireSupplementaire,
            ["id", "cours_id", "jour", "heure_debut", "heure_fin"],
            lambda db, eid: list(
                db.scalars(
                    select(CoursHoraireSupplementaire).where(
                        CoursHoraireSupplementaire.cours_id.in_(_sous_requete_cours_ecole(eid))
                    )
                )
            ),
        ),
        _Table(
            "CoursProfesseurs",
            cours_professeurs,
            ["cours_id", "professeur_id"],
            lambda db, eid: db.execute(
                select(cours_professeurs).where(cours_professeurs.c.cours_id.in_(_sous_requete_cours_ecole(eid)))
            ).all(),
        ),
        _Table(
            "Conversations",
            Conversation,
            ["id", "ecole_id", "saison_id", "nom", "type", "whatsapp_statut", "whatsapp_groupe_id"],
            lambda db, eid: list(db.scalars(select(Conversation).where(Conversation.ecole_id == eid))),
            colonne_ecole_id="ecole_id",
        ),
        _Table(
            "ConversationMembres",
            ConversationMembre,
            ["id", "conversation_id", "membre_type", "membre_id"],
            lambda db, eid: list(
                db.scalars(
                    select(ConversationMembre).where(
                        ConversationMembre.conversation_id.in_(_sous_requete_conversations_ecole(eid))
                    )
                )
            ),
        ),
        _Table(
            "Messages",
            Message,
            ["id", "conversation_id", "expediteur_id", "contenu", "created_at"],
            lambda db, eid: list(
                db.scalars(select(Message).where(Message.conversation_id.in_(_sous_requete_conversations_ecole(eid))))
            ),
        ),
        _Table(
            "MessageDeliveries",
            MessageDelivery,
            [
                "id", "message_id", "destinataire_id", "canal", "statut",
                "envoi_volontaire", "envoye_at", "recu_at", "lu_at",
            ],
            lambda db, eid: list(
                db.scalars(
                    select(MessageDelivery).where(MessageDelivery.message_id.in_(_sous_requete_messages_ecole(eid)))
                )
            ),
        ),
        _Table(
            "SeancesPresence",
            SeancePresence,
            ["id", "cours_id", "date"],
            lambda db, eid: list(
                db.scalars(select(SeancePresence).where(SeancePresence.cours_id.in_(_sous_requete_cours_ecole(eid))))
            ),
        ),
        _Table(
            "PresencesEleves",
            PresenceEleve,
            ["id", "seance_id", "eleve_id", "statut"],
            lambda db, eid: list(
                db.scalars(
                    select(PresenceEleve).where(PresenceEleve.seance_id.in_(_sous_requete_seances_ecole(eid)))
                )
            ),
        ),
        _Table(
            "PresencesProfs",
            PresenceProf,
            ["id", "seance_id", "professeur_id", "heure_debut_reelle", "heure_fin_reelle", "depassement_minutes"],
            lambda db, eid: list(
                db.scalars(select(PresenceProf).where(PresenceProf.seance_id.in_(_sous_requete_seances_ecole(eid))))
            ),
        ),
        _Table(
            "Choregraphies",
            Choregraphie,
            ["id", "cours_id", "nom", "horaire_repetition", "costume"],
            lambda db, eid: list(
                db.scalars(select(Choregraphie).where(Choregraphie.cours_id.in_(_sous_requete_cours_ecole(eid))))
            ),
        ),
        _Table(
            "ChoregraphiesEleves",
            choregraphies_eleves,
            ["choregraphie_id", "eleve_id"],
            lambda db, eid: db.execute(
                select(choregraphies_eleves).where(
                    choregraphies_eleves.c.choregraphie_id.in_(_sous_requete_choregraphies_ecole(eid))
                )
            ).all(),
        ),
        _Table(
            # Métadonnées seulement (voir docstring de tête) : jamais le
            # fichier vidéo lui-même.
            "Videos",
            Video,
            [
                "id", "ecole_id", "saison_id", "nom", "description", "lien_fichier",
                "poster", "date_publication", "uploaded_by", "duree_secondes",
            ],
            lambda db, eid: list(db.scalars(select(Video).where(Video.ecole_id == eid))),
            colonne_ecole_id="ecole_id",
        ),
        _Table(
            "ConsommationsIA",
            ConsommationIA,
            ["id", "ecole_id", "saison_id", "categorie", "cout_usd", "detail", "cree_le"],
            lambda db, eid: list(db.scalars(select(ConsommationIA).where(ConsommationIA.ecole_id == eid))),
            colonne_ecole_id="ecole_id",
        ),
        _Table(
            # Vidéos de chaque chorégraphie, dans l'ordre (les vidéos
            # elles-mêmes ne connaissent pas les chorégraphies).
            "ChoregraphiesVideos",
            choregraphies_videos,
            ["choregraphie_id", "video_id", "ordre"],
            lambda db, eid: db.execute(
                select(choregraphies_videos).where(
                    choregraphies_videos.c.choregraphie_id.in_(_sous_requete_choregraphies_ecole(eid))
                )
            ).all(),
        ),
    ]


def _valeur_cellule(obj: Any, nom: str) -> Any:
    """Une valeur de colonne, prête pour Excel (dates/heures en texte
    ISO — openpyxl gère mal un `datetime` avec fuseau horaire)."""
    valeur = obj[nom] if isinstance(obj, dict) else getattr(obj, nom)
    if isinstance(valeur, (dt.date, dt.datetime)):
        return valeur.isoformat()
    # Colonne JSON (champs des membres) : son texte JSON, relu à la restauration.
    if valeur is not None and hasattr(obj, "__table__") and isinstance(obj.__table__.c[nom].type, JSON):
        return json.dumps(valeur, ensure_ascii=False)
    return valeur


def _ligne_excel(obj: Any, colonnes: list[str]) -> list[Any]:
    return [_valeur_cellule(obj, nom) for nom in colonnes]


def nom_fichier(ecole: Ecole) -> str:
    from .excel_export import _slug  # même helper que l'export humain

    return f"{_slug(ecole.nom)}_{dt.date.today().isoformat()}_techBackup.xlsx"


def generer(db: Session, ecole: Ecole) -> bytes:
    classeur = Workbook()
    classeur.remove(classeur.active)

    feuille_ecole = classeur.create_sheet("École")
    feuille_ecole.append(COLONNES_ECOLE)
    feuille_ecole.append(_ligne_excel(ecole, COLONNES_ECOLE))

    with toutes_saisons(db):
        feuille_saisons = classeur.create_sheet("Saisons")
        feuille_saisons.append(COLONNES_SAISON)
        for saison in db.scalars(select(Saison).where(Saison.ecole_id == ecole.id).order_by(Saison.id)):
            feuille_saisons.append(_ligne_excel(saison, COLONNES_SAISON))

        for table in _construire_tables():
            feuille = classeur.create_sheet(table.feuille)
            feuille.append(table.colonnes)
            for ligne in table.lignes_ecole(db, ecole.id):
                feuille.append(_ligne_excel(ligne, table.colonnes))

    tampon = io.BytesIO()
    classeur.save(tampon)
    return tampon.getvalue()


def vider(db: Session, ecole_id: int, garder_compte_id: int | None = None, commit: bool = True) -> None:
    """"Supprimer Données École" ET 1re étape de `restaurer()` ci-dessous
    — supprime TOUT ce qui est propre à cette école (tables ci-dessus,
    ENFANTS D'ABORD, ordre inverse de `_construire_tables()`), sauf
    `garder_compte_id` (le compte admin conservé — voir receiver.py) et
    sa famille. La ligne École elle-même n'est jamais supprimée ici
    (l'identité de l'école — nom, codes d'accès — n'est pas "une donnée"
    au sens de cette fonction).

    `commit=False` (voir `restaurer()`) : NE PAS valider ici — sinon un
    échec plus loin dans la réinsertion laisserait la base VIDÉE sans
    être restaurée (perte de données constatée en test réel : la purge
    passait, la réinsertion échouait sur une ligne invalide, et
    `db.rollback()` côté receiver.py ne pouvait plus rien annuler
    puisque cette purge avait déjà été validée).

    Toutes les saisons sont vidées (spec §2.6), et seule la saison
    courante est gardée, vide (sauf le compte conservé)."""
    with toutes_saisons(db):
        _vider(db, ecole_id, garder_compte_id)
    if commit:
        db.commit()
    else:
        db.flush()


def _vider(db: Session, ecole_id: int, garder_compte_id: int | None) -> None:
    tables = _construire_tables()
    for table in reversed(tables):
        # Familles : gérées à part plus bas (celle du compte conservé ne
        # doit PAS être supprimée ici) — `Famille` reste dans
        # `_construire_tables()` uniquement pour figurer dans l'export.
        if table.objet is Famille:
            continue
        # Rôles : supprimés en cascade avec leur compte (voir
        # comptes/models.py, delete-orphan) — donc PAS ceux du compte
        # conservé, qui garde ses droits. Les supprimer aussi ici les
        # supprimerait deux fois.
        if table.objet in (RoleCompte, EmailCompte):
            continue
        lignes = table.lignes_ecole(db, ecole_id)
        if not lignes:
            continue
        if isinstance(table.objet, Table):
            cle_pk = list(table.objet.primary_key.columns)
            for ligne in lignes:
                condition = [col == ligne._mapping[col.name] for col in cle_pk]
                db.execute(delete(table.objet).where(*condition))
        else:
            for ligne in lignes:
                # Le compte admin conservé (et lui seul) survit à la
                # purge des Comptes — voir garder_compte_id ci-dessus.
                if table.objet is Compte and ligne.id == garder_compte_id:
                    continue
                db.delete(ligne)
    db.flush()

    # Familles : toutes supprimées SAUF celle du compte conservé (sinon
    # son propre famille_id pointerait dans le vide).
    famille_a_garder_id = None
    if garder_compte_id is not None:
        compte_garde = db.get(Compte, garder_compte_id)
        famille_a_garder_id = compte_garde.famille_id if compte_garde else None
        if compte_garde is not None:
            # Sa fiche de la saison précédente vient d'être supprimée.
            compte_garde.compte_precedent_id = None
    for famille in db.scalars(select(Famille).where(Famille.ecole_id == ecole_id)):
        if famille.id != famille_a_garder_id:
            db.delete(famille)
    db.flush()

    courante = saison_courante_id(db, ecole_id)
    db.execute(delete(Saison).where(Saison.ecole_id == ecole_id, Saison.id != courante))
    db.flush()


def restaurer(db: Session, ecole: Ecole, contenu: bytes) -> None:
    """"Importer sauvegarde" — ÉCRASE toutes les données actuelles de
    `ecole` (voir `vider()`, aucun compte conservé ici : le fichier de
    sauvegarde en contient déjà au moins un admin) puis réinsère tout
    depuis le fichier, TABLE PAR TABLE dans l'ordre parent -> enfant, en
    conservant les ids internes du fichier tels quels — sûr même dans une
    base partagée entre plusieurs écoles : on vient de libérer exactement
    ces ids (ils appartenaient à cette même école, qu'on vient de vider),
    aucune autre école ne peut les avoir pris entre-temps (une seule
    transaction). Seule la colonne ecole_id elle-même est forcée à
    `ecole.id` (jamais reprise du fichier) : permet de restaurer un
    fichier même si l'id de l'école a changé depuis (ex. après une
    réinstallation complète)."""
    classeur = load_workbook(io.BytesIO(contenu), read_only=True, data_only=True)
    with toutes_saisons(db):
        _restaurer(db, ecole, classeur)
    db.commit()
    _reajuster_sequences_postgres(db)


def _restaurer(db: Session, ecole: Ecole, classeur) -> None:
    vider(db, ecole.id, garder_compte_id=None, commit=False)
    # Saisons (spec §2.6) : celles du fichier remplacent la saison vide
    # laissée par `vider`. Une sauvegarde d'avant les saisons n'a pas cet
    # onglet : tout y est alors rangé dans la saison courante (voir
    # saisons/automatique.py, qui remplit `saison_id`).
    if "Saisons" in classeur.sheetnames:
        lignes = list(classeur["Saisons"].iter_rows(values_only=True))
        if len(lignes) > 1:
            db.execute(delete(Saison).where(Saison.ecole_id == ecole.id))
            en_tetes, *donnees = lignes
            for valeurs in donnees:
                champs = dict(zip(en_tetes, valeurs))
                champs["ecole_id"] = ecole.id
                db.add(Saison(**{nom: _valeur_restauree(Saison, nom, v) for nom, v in champs.items()}))
            db.flush()
    # Sauvegarde d'avant les rôles cumulables (§6.3bis) : un rôle unique
    # dans une colonne "role" de l'onglet Comptes, pas d'onglet
    # RolesComptes. Relu ici puis converti en fin de restauration.
    ancien_role_par_compte: dict[int, str] = {}
    ancien_email_par_compte: dict[int, str] = {}
    # Sauvegarde d'avant le module vidéo générique (2026-10-03) : chaque
    # vidéo portait son cours et sa chorégraphie, pas d'onglet
    # ChoregraphiesVideos. Relu ici, converti au fil de la restauration.
    anciens_liens_videos: list[dict] = []

    for table in _construire_tables():
        if table.feuille not in classeur.sheetnames:
            continue
        feuille = classeur[table.feuille]
        lignes = list(feuille.iter_rows(values_only=True))
        if not lignes:
            continue
        en_tetes, *donnees = lignes
        for valeurs in donnees:
            champs = dict(zip(en_tetes, valeurs))
            if table.colonne_ecole_id:
                champs[table.colonne_ecole_id] = ecole.id
            if table.objet is Compte and "role" in champs:
                ancien_role_par_compte[champs["id"]] = champs.pop("role")
            if table.objet is Compte and champs.get("email"):
                ancien_email_par_compte[champs["id"]] = champs.pop("email")
            if table.objet is Video and "cours_id" in champs:
                cours = db.get(Cours, champs["cours_id"])
                champs.setdefault("saison_id", cours.saison_id if cours is not None else None)
                if champs.get("choregraphie_id") is not None:
                    anciens_liens_videos.append(
                        {
                            "choregraphie_id": champs["choregraphie_id"],
                            "video_id": champs["id"],
                            "ordre": champs.get("ordre") or 0,
                        }
                    )
            # Colonnes disparues depuis la sauvegarde (ex. code de
            # récupération, retiré le 2026-10-01) : ignorées.
            connues = table.objet.c if isinstance(table.objet, Table) else table.objet.__table__.c
            champs = {
                nom: _valeur_restauree(table.objet, nom, valeur)
                for nom, valeur in champs.items()
                if nom in connues
            }
            if isinstance(table.objet, Table):
                db.execute(table.objet.insert().values(**champs))
            else:
                db.add(table.objet(**champs))
        db.flush()

    if anciens_liens_videos and "ChoregraphiesVideos" not in classeur.sheetnames:
        db.execute(choregraphies_videos.insert(), anciens_liens_videos)
        db.flush()
    if ancien_role_par_compte and "RolesComptes" not in classeur.sheetnames:
        _convertir_anciens_roles(db, ancien_role_par_compte)
    if ancien_email_par_compte and "EmailsComptes" not in classeur.sheetnames:
        for compte_id, email in ancien_email_par_compte.items():
            for adresse in separer_emails(email):
                db.add(EmailCompte(compte_id=compte_id, email=adresse))
        db.flush()
    _anciens_profs_en_groupe(db, ecole.id)
    _anciens_eleves_des_cours(db, ecole.id, classeur)
    _anciens_champs_des_eleves(db, ecole.id, classeur)
    # Sauvegarde d'avant l'email du payeur (27/10/2026) : mêmes familles.
    comptes = classeur["Comptes"] if "Comptes" in classeur.sheetnames else None
    if comptes is not None and "payer_email" not in next(comptes.iter_rows(values_only=True), ()):
        db.flush()
        reprendre_payeurs(db.connection(), ecole.id)
        db.expire_all()


def _anciens_champs_des_eleves(db: Session, ecole_id: int, classeur) -> None:
    """Sauvegarde d'avant l'étape 4c (27/10/2026) : naissance, adresse et
    santé étaient des colonnes de ProfilsEleves. Ils deviennent les champs
    marqués de chaque saison (members.fields.KNOWN), avec leurs réponses."""
    if "ChampsMembres" in classeur.sheetnames:
        en_tetes = next(classeur["ChampsMembres"].iter_rows(values_only=True), ())
        if "key" in en_tetes:
            return
    anciennes = {"birth_date": "date_naissance", "address": "adresse", "allergies": "allergies",
                 "medical_treatment": "traitement_medical", "important_info": "informations_importantes"}
    with toutes_saisons(db):
        for saison_id in db.scalars(select(Saison.id).where(Saison.ecole_id == ecole_id)).all():
            champs = known(db, ecole_id, saison_id)
            profils = db.scalars(
                select(ProfilEleve).join(Compte, Compte.id == ProfilEleve.compte_id).where(Compte.saison_id == saison_id)
            ).all()
            for profil in profils:
                for cle, colonne in anciennes.items():
                    valeur = getattr(profil, colonne)
                    if isinstance(valeur, dt.date):
                        valeur = valeur.isoformat()
                    if valeur not in (None, ""):
                        # Requête directe : les saisons passées sont en lecture
                        # seule pour l'ORM (saisons/portee.py).
                        db.execute(
                            insert(MemberValue).values(
                                member_id=profil.compte_id, field_id=champs[cle].id, value=valeur,
                                updated_at=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None),
                            )
                        )
        db.flush()


def _anciens_eleves_des_cours(db: Session, ecole_id: int, classeur) -> None:
    """Sauvegarde d'avant le 27/10/2026 : les cours n'avaient pas de groupe et
    leurs élèves étaient dans l'onglet ElevesCours. Chaque cours reçoit son
    groupe (groups/courses.py), qui reprend ces élèves."""
    with toutes_saisons(db):
        sans_groupe = {}
        for cours in db.scalars(select(Cours).where(Cours.ecole_id == ecole_id, Cours.group_id.is_(None))).all():
            sans_groupe[cours.id] = courses.create(db, ecole_id, cours.saison_id, cours.nom).id
            # Requête directe, comme une migration : les cours des saisons
            # passées sont en lecture seule pour l'ORM (saisons/portee.py).
            db.execute(update(Cours).where(Cours.id == cours.id).values(group_id=sans_groupe[cours.id]))
            db.expire(cours, ["group_id"])
        if "ElevesCours" not in classeur.sheetnames:
            return
        lignes = list(classeur["ElevesCours"].iter_rows(values_only=True))
        if not lignes:
            return
        en_tetes, *donnees = lignes
        for valeurs in donnees:
            ligne = dict(zip(en_tetes, valeurs))
            group_id = sans_groupe.get(ligne.get("cours_id"))
            if group_id is not None and ligne.get("eleve_id") is not None:
                courses.add(db, group_id, ligne["eleve_id"])
        db.flush()


def _anciens_profs_en_groupe(db: Session, ecole_id: int) -> None:
    """Sauvegarde d'avant le 27/10/2026 : les rôles Professeur et Trésorier
    étaient des lignes de RolesComptes ; ils deviennent le groupe « Profs »
    (groups/teachers.py) et le groupe 🔒 « Accès au Financier »
    (groups/rights.py)."""
    with toutes_saisons(db):
        for role in roles.ROLES_EN_GROUPE:
            ids = db.scalars(
                select(RoleCompte.compte_id).where(
                    RoleCompte.role == role, RoleCompte.compte_id.in_(_sous_requete_comptes_ecole(ecole_id))
                )
            ).all()
            db.execute(delete(RoleCompte).where(RoleCompte.role == role, RoleCompte.compte_id.in_(ids)))
            for compte_id in ids:
                compte = db.get(Compte, compte_id)
                db.expire(compte, ["roles"])
                if role == roles.PROFESSEUR:
                    teachers.add(db, compte)
                else:
                    rights.add(db, compte, roles.DROIT_FINANCIER)


def _convertir_anciens_roles(db: Session, ancien_role_par_compte: dict[int, str]) -> None:
    """Même conversion que la migration Alembic des rôles cumulables : un
    rôle par compte, et Owner pour le plus ancien admin (§2.4)."""
    for compte_id, role in ancien_role_par_compte.items():
        db.add(RoleCompte(compte_id=compte_id, role=role))
    admins = sorted(cid for cid, role in ancien_role_par_compte.items() if role == roles.ADMIN)
    if admins:
        db.add(RoleCompte(compte_id=admins[0], role=roles.OWNER))
    db.flush()


def _valeur_restauree(objet: type | Table, nom: str, valeur: Any) -> Any:
    """Inverse de `_valeur_cellule()` : une date/heure ISO redevient un
    vrai `date`/`datetime` pour les colonnes qui l'attendent (openpyxl
    relit un texte, pas un type Python)."""
    if isinstance(objet, Table):
        return valeur
    colonne = objet.__table__.columns.get(nom)
    if colonne is None:
        return valeur
    if valeur is None:
        # Une cellule Excel vide redevient `None` à la lecture (openpyxl
        # ne distingue pas "chaîne vide" de "case vide") — or une colonne
        # texte NOT NULL ne pouvait, par construction, contenir QUE ""
        # avant l'export (jamais NULL, sinon la contrainte aurait déjà
        # échoué bien avant). Sans ce repli, restaurer une ligne avec un
        # tel champ (ex. Video.lien_fichier d'une vidéo sans fichier
        # encore uploadé) viole la contrainte NOT NULL — constaté en test
        # réel (voir "Silhouettes — filage" dans les données de seed).
        if not colonne.nullable and colonne.type.python_type is str:
            return ""
        return None
    if isinstance(colonne.type, JSON):
        return json.loads(valeur) if isinstance(valeur, str) else valeur
    type_python = colonne.type.python_type if hasattr(colonne.type, "python_type") else None
    if type_python is dt.datetime and isinstance(valeur, str):
        return dt.datetime.fromisoformat(valeur)
    if type_python is dt.date and isinstance(valeur, str):
        return dt.date.fromisoformat(valeur)
    return valeur


def _reajuster_sequences_postgres(db: Session) -> None:
    """SQLite retrouve seul le bon "prochain id" après une insertion à id
    explicite (ROWID standard) — Postgres, lui, a une vraie séquence à
    part qui NE bouge PAS toute seule dans ce cas : sans ce réajustement,
    le prochain compte/cours/... créé normalement après une restauration
    risquerait un id déjà pris (collision). No-op sur SQLite (déploiement
    actuel, voir db/database.py) — sécurité pour un futur passage à
    Postgres (voir spec/SPEC.md section 1)."""
    if db.bind.dialect.name != "postgresql":
        return
    # ProfilEleve exclu : sa clé primaire (compte_id) n'est pas une
    # séquence auto-incrémentée (voir eleves/models.py), rien à réajuster.
    tables_avec_id = [
        Saison, Famille, Compte, ContactEleve, Cours, CoursHoraireSupplementaire,
        Conversation, ConversationMembre, Message, MessageDelivery, SeancePresence,
        PresenceEleve, PresenceProf, Choregraphie, Video, ConsommationIA,
    ]
    for classe in tables_avec_id:
        nom_table = classe.__tablename__
        db.execute(
            text(
                f"SELECT setval(pg_get_serial_sequence('{nom_table}', 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {nom_table}), 1))"
            )
        )
