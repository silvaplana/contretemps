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
from dataclasses import dataclass
from typing import Any, Callable

from choregraphies.models import Choregraphie, choregraphies_eleves
from comptes.models import Compte, Famille
from cours.models import Cours, CoursHoraireSupplementaire, cours_professeurs, eleves_cours
from eleves.models import ContactEleve, ProfilEleve
from messagerie.models import Conversation, ConversationMembre, Message, MessageDelivery
from openpyxl import Workbook, load_workbook
from presence.models import PresenceEleve, PresenceProf, SeancePresence
from sqlalchemy import Table, delete, select, text
from sqlalchemy.orm import Session
from videos.models import Video

from .models import Ecole

COLONNES_ECOLE = [
    "id",
    "nom",
    "code_postal",
    "code_acces_admin",
    "code_acces_prof",
    "code_acces_eleve",
    "created_at",
]


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
            ["id", "ecole_id", "created_at"],
            lambda db, eid: list(db.scalars(select(Famille).where(Famille.ecole_id == eid))),
            colonne_ecole_id="ecole_id",
        ),
        _Table(
            "Comptes",
            Compte,
            [
                "id", "ecole_id", "famille_id", "role", "nom", "prenom", "email", "telephone",
                "hashed_password_ou_code", "code_recuperation", "created_at",
            ],
            lambda db, eid: list(db.scalars(select(Compte).where(Compte.ecole_id == eid))),
            colonne_ecole_id="ecole_id",
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
            ["id", "ecole_id", "nom", "jour", "heure_debut", "heure_fin", "salle", "descriptif", "ordre"],
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
            "ElevesCours",
            eleves_cours,
            ["eleve_id", "cours_id"],
            lambda db, eid: db.execute(
                select(eleves_cours).where(eleves_cours.c.cours_id.in_(_sous_requete_cours_ecole(eid)))
            ).all(),
        ),
        _Table(
            "Conversations",
            Conversation,
            ["id", "ecole_id", "nom", "type", "whatsapp_statut", "whatsapp_groupe_id"],
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
                "id", "cours_id", "choregraphie_id", "nom", "description", "lien_fichier",
                "poster", "date_publication", "uploaded_by", "duree_secondes", "ordre",
            ],
            lambda db, eid: list(db.scalars(select(Video).where(Video.cours_id.in_(_sous_requete_cours_ecole(eid))))),
        ),
    ]


def _valeur_cellule(obj: Any, nom: str) -> Any:
    """Une valeur de colonne, prête pour Excel (dates/heures en texte
    ISO — openpyxl gère mal un `datetime` avec fuseau horaire)."""
    valeur = obj[nom] if isinstance(obj, dict) else getattr(obj, nom)
    if isinstance(valeur, (dt.date, dt.datetime)):
        return valeur.isoformat()
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
    puisque cette purge avait déjà été validée)."""
    tables = _construire_tables()
    for table in reversed(tables):
        # Familles : gérées à part plus bas (celle du compte conservé ne
        # doit PAS être supprimée ici) — `Famille` reste dans
        # `_construire_tables()` uniquement pour figurer dans l'export.
        if table.objet is Famille:
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
    for famille in db.scalars(select(Famille).where(Famille.ecole_id == ecole_id)):
        if famille.id != famille_a_garder_id:
            db.delete(famille)
    if commit:
        db.commit()
    else:
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
    vider(db, ecole.id, garder_compte_id=None, commit=False)

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
            champs = {nom: _valeur_restauree(table.objet, nom, valeur) for nom, valeur in champs.items()}
            if isinstance(table.objet, Table):
                db.execute(table.objet.insert().values(**champs))
            else:
                db.add(table.objet(**champs))
        db.flush()

    db.commit()
    _reajuster_sequences_postgres(db)


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
        Famille, Compte, ContactEleve, Cours, CoursHoraireSupplementaire,
        Conversation, ConversationMembre, Message, MessageDelivery, SeancePresence,
        PresenceEleve, PresenceProf, Choregraphie, Video,
    ]
    for classe in tables_avec_id:
        nom_table = classe.__tablename__
        db.execute(
            text(
                f"SELECT setval(pg_get_serial_sequence('{nom_table}', 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {nom_table}), 1))"
            )
        )
