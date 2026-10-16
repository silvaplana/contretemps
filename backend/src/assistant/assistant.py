"""Assistant de l'onglet Docs (prototype, Seb 15 octobre ; plan
documents-phase-contretemps.md, étape 5 bis).

Une conversation avec Claude qui connaît l'endroit où l'on est dans Docs,
lit les dossiers et fichiers que la personne a le droit de voir, et
PROPOSE des actions (créer un dossier, un fichier texte, déplacer,
renommer) sans jamais les faire : chaque proposition part à l'écran sous
forme de carte « Faire / Annuler », et c'est l'appli qui l'exécute, avec
les droits et l'« Annuler » habituels de Docs.

Les conversations restent en mémoire du serveur (prototype : perdues à son
redémarrage). Elles sont rejouées telles quelles à chaque tour : jamais
modifiées, seulement complétées (les blocs de réflexion du modèle doivent
revenir à l'identique).
"""

from __future__ import annotations

import io
import json
import logging
import os
import tempfile
import threading
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import anthropic
from documents.ports import Member
from documents.service import DocError, Documents
from documents.storage import guess_mime

from .donnees import NOMS as OUTILS_ECOLE
from .fichier_appli import CONSIGNE_FICHIER, OUTIL_FICHIER, FichierAppli
from .donnees import OUTILS_DONNEES, DonneesEcole
from .lecture import contenu_pour_claude
from .modifications import OUTIL_MODIFICATIONS

logger = logging.getLogger(__name__)

MODELE = "claude-opus-5-5"
# Modèles au choix dans le panneau du coût (Seb, 15 octobre) : libellé.
MODELES = {
    "claude-opus-5-5": "Opus 5.5",
    "claude-sonnet-5-5": "Sonnet 5.5",
    "claude-haiku-5-5": "Haiku 5.5",
    "claude-fable-5-1": "Fable 5.1",
}
# Prix en dollars par million de jetons (entrée, sortie, lecture du cache).
PRIX = {
    "claude-opus-5-5": (4.0, 20.0, 0.20),
    "claude-sonnet-5-5": (2.0, 10.0, 0.20),
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
    "claude-fable-5-1": (10.0, 50.0, 0.25),
    # Modèles de repli possibles, si le premier décline la demande.
    "claude-opus-5": (5.0, 25.0, 0.50),
    "claude-opus-4-8": (5.0, 25.0, 0.50),
}
TOURS_MAX = 10  # appels d'outils enchaînés au plus pour une seule question

ESPACES = {"public": "Public", "private": "Privé", "personal": "Personnel"}

CONSIGNE = """Tu es l'assistant de Contretemps, l'appli d'une école de danse gérée par une \
association loi 1901. Tu aides la personne à retrouver, lire, résumer et ranger les dossiers \
et fichiers de l'onglet « Docs », et tu réponds aux questions sur les données de l'école \
(élèves, cours, professeurs, présences, heures des professeurs, chorégraphies, inscriptions, \
saisons) grâce aux outils de lecture : ne réponds jamais de mémoire sur ces données, \
consulte-les. Tu ne vois que ce que la personne a le droit de voir, et jamais les \
informations de santé. Tu ne modifies aucune donnée de l'école.

Les espaces : « Public » (visible par tous), « Privé » (l'équipe ; un dossier « Permanent » \
et un dossier par saison), « Personnel » (les fichiers de la personne seule). Les éléments \
ont un numéro (id) : sers-t'en pour les outils, jamais dans tes réponses.

Règles :
- Réponds en français, simplement et brièvement, comme à un bénévole pressé. Pas de jargon \
technique, pas de numéros d'éléments : nomme les fichiers et dossiers par leur nom.
- Ne te présente jamais comme une « IA » : tu es « l'assistant ».
- Utilise les outils pour regarder avant de répondre ; ne devine jamais le contenu d'un \
dossier ou d'un fichier.
- Pour toute modification (créer, ranger, renommer), utilise un outil « proposer_… ». La \
proposition s'affiche à la personne avec « Faire » et « Annuler » : elle décide. Dis-le en \
une phrase, sans prétendre que c'est fait. Tu sauras au message suivant si elle l'a faite.
- Un message commence par le contexte (où la personne se trouve dans Docs) : sers-t'en \
pour comprendre « ce dossier » ou « ce fichier ».

Tu peux aussi proposer des changements dans les données de l'école (élèves, inscriptions aux \
cours, paiements, présences, heures des professeurs, cours, chorégraphies) avec \
« proposer_modifications » : lis d'abord les données, puis regroupe tous les changements d'une \
demande en un seul appel. La personne voit une carte récapitulative, décoche ce qu'elle ne veut \
pas et valide : ne prétends jamais que c'est fait avant de l'apprendre au message suivant.

Tu as accès à internet : « web_search » pour chercher (actualité, lois et règles des \
associations, sites officiels…) et « web_fetch » pour lire une page dont l'adresse est dans la \
conversation (par exemple le site de l'école). Cite tes sources. Ne mets jamais de données \
personnelles des élèves, familles ou professeurs (noms, contacts, adresses) dans une recherche.

Tu disposes aussi d'un ordinateur (l'outil d'exécution de code, Python, sans accès à internet) pour \
calculer, tracer des courbes (matplotlib) et fabriquer des fichiers (PDF, Excel, Word, \
PowerPoint, images). Pour travailler sur un fichier de l'école, copie-le d'abord dans \
l'ordinateur avec « copier_fichier_dans_l_ordinateur ». Pour remettre un fichier à la \
personne, enregistre-le dans le dossier $OUTPUT_DIR, dans la même commande que celle qui le \
fabrique, et liste ce dossier pour vérifier : il lui sera proposé avec « Faire / Annuler », \
rangé dans le dossier qu'elle regarde. Donne-lui un nom clair en français (ex. \
« Courbe des inscriptions.pdf »)."""
CONSIGNE += CONSIGNE_FICHIER


def _prop(type_, description, **autres):
    return {"type": type_, "description": description, **autres}


ESPACE = _prop("string", "Espace : public, private ou personal.", enum=list(ESPACES))
DOSSIER = _prop(["integer", "null"], "Numéro du dossier ; null pour la racine de l'espace.")


def _outil(nom: str, description: str, proprietes: dict) -> dict:
    return {
        "name": nom,
        "description": description,
        "strict": True,
        "eager_input_streaming": True,
        "input_schema": {
            "type": "object",
            "properties": proprietes,
            "required": list(proprietes),
            "additionalProperties": False,
        },
    }


OUTILS = [
    _outil("lister_dossier", "Liste les dossiers et fichiers d'un dossier (ou de la racine d'un espace).",
           {"espace": ESPACE, "dossier_id": DOSSIER}),
    _outil("chercher", "Cherche des dossiers et fichiers par leur nom dans un espace.",
           {"espace": ESPACE, "texte": _prop("string", "Mots à chercher dans les noms.")}),
    _outil("fichiers_recents", "Les derniers fichiers modifiés, tous espaces confondus.", {}),
    _outil("lire_fichier", "Lit le contenu d'un fichier (PDF, Word, Excel, texte, photo).",
           {"fichier_id": _prop("integer", "Numéro du fichier.")}),
    _outil("copier_fichier_dans_l_ordinateur",
           "Copie un fichier de l'école dans ton ordinateur (outil d'exécution de code) pour le traiter en Python. "
           "Il y apparaît sous son nom ; retrouve-le avec `find / -name '<nom>' 2>/dev/null`.",
           {"fichier_id": _prop("integer", "Numéro du fichier.")}),
    _outil("proposer_creer_dossier", "Propose de créer un dossier (la personne confirme).",
           {"espace": ESPACE, "dossier_parent_id": DOSSIER, "nom": _prop("string", "Nom du dossier.")}),
    _outil("proposer_creer_fichier_texte",
           "Propose de créer un fichier texte rédigé par toi (la personne confirme). Nom en .txt ou .md.",
           {"espace": ESPACE, "dossier_parent_id": DOSSIER, "nom": _prop("string", "Nom du fichier."),
            "contenu": _prop("string", "Texte complet du fichier.")}),
    _outil("proposer_deplacer", "Propose de déplacer un dossier ou un fichier (la personne confirme).",
           {"element_id": _prop("integer", "Numéro de l'élément à déplacer."), "espace": ESPACE,
            "dossier_destination_id": DOSSIER}),
    _outil("proposer_renommer", "Propose de renommer un dossier ou un fichier (la personne confirme).",
           {"element_id": _prop("integer", "Numéro de l'élément."),
            "nouveau_nom": _prop("string", "Nouveau nom.")}),
    # Ordinateur d'Anthropic (Python, sans internet) : courbes, calculs, PDF,
    # Excel, Word, PowerPoint. Les fichiers déposés dans $OUTPUT_DIR
    # reviennent ici (voir _fichiers_produits).
    {"type": "code_execution_20260521", "name": "code_execution"},
    # Internet (Seb, 16 octobre) : recherche et lecture de pages. Versions
    # sans filtrage par code, pour ne pas créer un second ordinateur à côté
    # de code_execution. web_fetch ne lit que des adresses déjà citées dans
    # la conversation (par la personne ou par une recherche).
    {"type": "web_search_20250305", "name": "web_search", "max_uses": 5,
     "user_location": {"type": "approximate", "country": "FR", "timezone": "Europe/Paris"}},
    {"type": "web_fetch_20250910", "name": "web_fetch", "max_uses": 5},
    # Données de l'école (élèves, cours, présences…), en lecture, avec les
    # droits de la personne (voir donnees.py).
    *OUTILS_DONNEES,
    # Modifications des données de l'école, validées par la personne sur une
    # carte récapitulative (voir modifications.py).
    OUTIL_MODIFICATIONS,
    # Fichier de l'appli ouvert : écrire ses deux formulaires (voir fichier_appli.py).
    OUTIL_FICHIER,
]
TAILLE_MAX_PRODUIT = 50 * 1024 * 1024
# Fichiers glissés dans l'assistant (pièces jointes d'une question).
TAILLE_MAX_PIECE = 20 * 1024 * 1024
PIECES_MAX = 5
PIECES_EN_ATTENTE_MAX = 30
# Données à copier aussi dans l'ordinateur, pour calculer dessus.
POUR_L_ORDINATEUR = (".xlsx", ".xls", ".csv", ".json", ".ods")
EN_ATTENTE_MAX = 40  # fichiers produits gardés en mémoire, en attente de « Faire »


class AssistantIndisponible(Exception):
    """Message lisible, montré tel quel."""


def cout_usd(modele: str, usage) -> float:
    entree, sortie, cache = PRIX.get(modele, PRIX[MODELE])
    lu = getattr(usage, "cache_read_input_tokens", 0) or 0
    ecrit = getattr(usage, "cache_creation_input_tokens", 0) or 0
    serveur = getattr(usage, "server_tool_use", None)
    recherches = getattr(serveur, "web_search_requests", 0) or 0
    # Recherche sur internet : 10 $ les 1 000 ; la lecture de pages ne
    # coûte que ses jetons.
    return (
        usage.input_tokens * entree + ecrit * entree * 1.25 + lu * cache + usage.output_tokens * sortie
    ) / 1e6 + recherches * 0.01


@dataclass
class Conversation:
    id: str
    org_id: int
    person_id: int
    messages: list = field(default_factory=list)
    cout_usd: float = 0.0
    # Ordinateur de la conversation (réutilisé d'un message à l'autre : les
    # fichiers copiés et calculés y restent).
    container_id: str | None = None
    # Une ligne par question : modèle, nombre d'appels, jetons, coût.
    tours: list = field(default_factory=list)
    verrou: threading.Lock = field(default_factory=threading.Lock)


def _evenement(**donnees) -> str:
    return f"data: {json.dumps(donnees, ensure_ascii=False)}\n\n"


class Assistant:
    def __init__(
        self, documents: Documents, client: anthropic.Anthropic | None = None, noter_cout=None, cout_saison=None
    ) -> None:
        """`noter_cout(db, org_id, cout_usd, detail)` : reporte le coût de
        chaque question dans « Usage des ressources & IA » (catégorie
        « Chat documents », branchée par app/main.py)."""
        self.documents = documents
        self._client = client
        self.noter_cout = noter_cout
        # cout_saison(db, org_id) : cumul « Chat documents » de la saison.
        self.cout_saison = cout_saison
        self.conversations: dict[str, Conversation] = {}
        # Fichiers fabriqués par l'ordinateur, en attente de « Faire » :
        # jeton -> (org_id, person_id, nom, contenu).
        self.produits: dict[str, tuple[int, int, str, bytes]] = {}
        self.donnees = DonneesEcole()
        # Branché par app/main.py (services des élèves, cours, présences…).
        self.modifications = None
        # Fichiers glissés dans l'assistant, en attente de la question :
        # jeton -> (org_id, person_id, nom, contenu).
        self.pieces: dict[str, tuple[int, int, str, bytes]] = {}
        self.fichier_appli = FichierAppli(documents)

    @property
    def actif(self) -> bool:
        return self._client is not None or bool(os.environ.get("ANTHROPIC_API_KEY"))

    def _claude(self) -> anthropic.Anthropic:
        if self._client is None:
            self._client = anthropic.Anthropic()
        return self._client

    def conversation(self, member: Member, conversation_id: str | None) -> Conversation:
        conv = self.conversations.get(conversation_id or "")
        if conv is None or conv.org_id != member.org_id or conv.person_id != member.person_id:
            conv = Conversation(id=uuid.uuid4().hex, org_id=member.org_id, person_id=member.person_id)
            self.conversations[conv.id] = conv
        return conv

    # ------------------------------------------------------------------
    # Contexte de chaque message
    # ------------------------------------------------------------------

    def _contexte(self, db, member: Member, contexte: dict) -> str:
        espace = contexte.get("space") if contexte.get("space") in ESPACES else "private"
        lignes = [f"Contexte : la personne est dans l'espace « {ESPACES[espace]} »"]
        dossier_id = contexte.get("folder_id")
        if dossier_id:
            try:
                d = self.documents.detail(db, member, int(dossier_id))
                chemin = " › ".join([ESPACES[espace], *(p["name"] for p in d.get("path", [])), d["name"]])
                contexte["lieu"] = chemin
                lignes[0] = f"Contexte : la personne regarde le dossier « {chemin} » (id {d['id']})"
            except (DocError, ValueError):
                pass
        else:
            lignes[0] += ", à la racine"
        if contexte.get("recents"):
            lignes.append("Elle regarde la liste « Récents ».")
        selection = contexte.get("selection_id")
        if selection:
            try:
                s = self.documents.detail(db, member, int(selection))
                genre = "le dossier" if s["kind"] == "folder" else "le fichier"
                lignes.append(f"Elle a sélectionné {genre} « {s['name']} » (id {s['id']}).")
            except (DocError, ValueError):
                pass
        plusieurs = contexte.get("selection_ids") or []
        if len(plusieurs) > 1:
            noms = []
            for identifiant in plusieurs[:50]:
                try:
                    s = self.documents.detail(db, member, int(identifiant))
                    noms.append(f"« {s['name']} » (id {s['id']})")
                except (DocError, ValueError):
                    pass
            if noms:
                lignes.append(f"Elle a sélectionné {len(noms)} éléments : {', '.join(noms)}.")
        if contexte.get("app_id"):
            try:
                lignes.append(self.fichier_appli.contexte(db, member, int(contexte["app_id"]), contexte.get("form")))
            except (DocError, ValueError):
                pass
        for issue in contexte.get("actions") or []:
            lignes.append(f"Suite à ta proposition : {str(issue)[:300]}")
        return "\n".join(lignes)

    # ------------------------------------------------------------------
    # Outils
    # ------------------------------------------------------------------

    @staticmethod
    def _ligne(e: dict) -> str:
        if e["kind"] == "app":
            return f"- [fichier de l'appli] {e['name']} (id {e['id']})"
        if e["kind"] == "folder":
            return f"- [dossier] {e['name']} (id {e['id']}, {e.get('child_count') or 0} éléments)"
        date = (e.get("updated_at") or "")[:10]
        auteur = f", par {e['updated_by']}" if e.get("updated_by") else ""
        return f"- [fichier] {e['name']} (id {e['id']}, {(e.get('size') or 0) // 1024} Ko, modifié le {date}{auteur})"

    def _executer(self, db, member: Member, nom: str, args: dict, compte=None) -> tuple[list[dict] | str, dict | None]:
        """(résultat pour Claude, éventuelle carte d'action pour l'écran)."""
        if nom == "proposer_modifications":
            if compte is None or self.modifications is None:
                raise ValueError("modifications indisponibles")
            return self.modifications.proposer(db, compte, member.org_id, member.person_id, args)
        if nom in OUTILS_ECOLE:
            if compte is None:
                raise ValueError("données de l'école indisponibles")
            return self.donnees.executer(db, compte, member.org_id, nom, args), None
        d = self.documents
        if nom == "lister_dossier":
            x = d.browse(db, member, args["espace"], args["dossier_id"])
            if not x["items"]:
                return "Ce dossier est vide.", None
            return "\n".join(self._ligne(e) for e in x["items"]), None
        if nom == "chercher":
            trouves = d.search(db, member, args["espace"], args["texte"])
            if not trouves:
                return "Rien trouvé.", None
            return "\n".join(
                self._ligne(e) + " dans " + (" › ".join(p["name"] for p in e.get("path", [])) or ESPACES[args["espace"]])
                for e in trouves
            ), None
        if nom == "fichiers_recents":
            recents = d.recent(db, member, limit=20)
            return "\n".join(
                self._ligne(e) + " dans " + " › ".join([ESPACES.get(e["space"], ""), *(p["name"] for p in e.get("path", []))])
                for e in recents
            ) or "Aucun fichier.", None
        if nom == "modifier_fichier_appli":
            return self.fichier_appli.modifier(db, member, args)
        if nom == "lire_fichier":
            if d.detail(db, member, args["fichier_id"])["kind"] == "app":
                return self.fichier_appli.lire(db, member, args["fichier_id"]), None
            chemin, nom_fichier, mime = d.content(db, member, args["fichier_id"])
            return contenu_pour_claude(chemin, nom_fichier, mime), None
        if nom == "copier_fichier_dans_l_ordinateur":
            chemin, nom_fichier, mime = d.content(db, member, args["fichier_id"])
            envoye = self._claude().files.upload(file=(nom_fichier, chemin.read_bytes(), mime))
            # Le bloc container_upload accompagne le résultat (voir repondre).
            return f"COPIE:{envoye.id}:{nom_fichier}", None
        return self._proposer(db, member, nom, args)

    def _nom_dossier(self, db, member: Member, espace: str, dossier_id: int | None) -> str:
        if dossier_id is None:
            return ESPACES[espace]
        dossier = self.documents.detail(db, member, dossier_id)
        return " › ".join([ESPACES[espace], *(p["name"] for p in dossier.get("path", [])), dossier["name"]])

    def _proposer(self, db, member: Member, nom: str, args: dict) -> tuple[str, dict]:
        carte = {"id": uuid.uuid4().hex[:12], "kind": nom.removeprefix("proposer_"), **args}
        if nom == "proposer_creer_dossier":
            ou = self._nom_dossier(db, member, args["espace"], args["dossier_parent_id"])
            carte["libelle"] = f"Créer le dossier « {args['nom']} » dans {ou}"
        elif nom == "proposer_creer_fichier_texte":
            ou = self._nom_dossier(db, member, args["espace"], args["dossier_parent_id"])
            carte["libelle"] = f"Créer le fichier « {args['nom']} » dans {ou}"
        elif nom == "proposer_deplacer":
            element = self.documents.detail(db, member, args["element_id"])
            ou = self._nom_dossier(db, member, args["espace"], args["dossier_destination_id"])
            carte["libelle"] = f"Déplacer « {element['name']} » dans {ou}"
        elif nom == "proposer_renommer":
            element = self.documents.detail(db, member, args["element_id"])
            carte["libelle"] = f"Renommer « {element['name']} » en « {args['nouveau_nom']} »"
        else:
            raise DocError(422, f"Outil inconnu : {nom}")
        return (
            f"Proposition affichée à la personne : « {carte['libelle']} ». Elle décidera (Faire / Annuler) ; "
            "rien n'est fait pour l'instant.",
            carte,
        )

    def _fichiers_produits(self, member: Member, reponse, contexte: dict) -> list[dict]:
        """Fichiers déposés par l'ordinateur dans $OUTPUT_DIR : téléchargés,
        gardés en attente, et proposés en carte « Ajouter … dans … »."""
        cartes = []
        for bloc in reponse.content:
            if getattr(bloc, "type", "") != "bash_code_execution_tool_result":
                continue
            resultat = bloc.content
            if getattr(resultat, "type", "") != "bash_code_execution_result":
                continue
            for sortie in getattr(resultat, "content", None) or []:
                file_id = getattr(sortie, "file_id", None)
                if not file_id:
                    continue
                try:
                    meta = self._claude().files.retrieve_metadata(file_id)
                    contenu = self._claude().files.download(file_id).read()
                except anthropic.APIError:
                    logger.exception("Fichier produit illisible (%s)", file_id)
                    continue
                nom = (meta.filename or "fichier").replace("/", "-").replace("\\", "-").strip() or "fichier"
                if len(contenu) > TAILLE_MAX_PRODUIT:
                    continue
                while len(self.produits) >= EN_ATTENTE_MAX:
                    self.produits.pop(next(iter(self.produits)))
                jeton = uuid.uuid4().hex
                self.produits[jeton] = (member.org_id, member.person_id, nom, contenu)
                espace = contexte.get("space") if contexte.get("space") in ESPACES else "private"
                dossier = contexte.get("folder_id") if not contexte.get("recents") else None
                cartes.append({
                    "id": jeton[:12], "kind": "ajouter_fichier", "jeton": jeton, "nom": nom,
                    "espace": espace, "dossier_parent_id": dossier, "taille": len(contenu),
                    "libelle": f"Ajouter « {nom} » dans {contexte.get('lieu') or ESPACES[espace]}",
                })
        return cartes

    def deposer_piece(self, member: Member, nom: str, contenu: bytes) -> dict:
        """Fichier glissé dans l'assistant : gardé jusqu'à la question qui
        l'accompagne (voir _blocs_pieces)."""
        if len(contenu) > TAILLE_MAX_PIECE:
            raise DocError(413, f"Fichier trop gros pour l'assistant ({TAILLE_MAX_PIECE // (1024 * 1024)} Mo au plus).")
        nom = (nom or "fichier").replace("/", "-").replace("\\", "-").strip() or "fichier"
        while len(self.pieces) >= PIECES_EN_ATTENTE_MAX:
            self.pieces.pop(next(iter(self.pieces)))
        jeton = uuid.uuid4().hex
        self.pieces[jeton] = (member.org_id, member.person_id, nom, contenu)
        return {"id": jeton, "nom": nom, "taille": len(contenu)}

    def _piece_de_docs(self, db, member: Member, jeton: str) -> tuple[str, bytes] | str | None:
        """Élément de Docs glissé dans l'assistant (« doc:<id> »), avec les
        droits de la personne : (nom, contenu) d'un fichier, ou une phrase
        pour un dossier."""
        try:
            identifiant = int(jeton.removeprefix("doc:"))
            detail = self.documents.detail(db, member, identifiant)
            if detail["kind"] == "folder":
                return f"La personne a joint le dossier « {detail['name']} » (id {identifiant})."
            chemin, nom, _ = self.documents.content(db, member, identifiant)
            return nom, Path(chemin).read_bytes()
        except (DocError, ValueError, OSError):
            return None

    def _blocs_pieces(self, member: Member, jetons: list[str], db=None) -> list[dict]:
        """Ce que Claude reçoit des fichiers glissés (de l'ordinateur ou de
        Docs) : le contenu (PDF et photos lus directement, Word / Excel /
        texte en texte) et, pour les données, une copie dans son ordinateur."""
        blocs = []
        for jeton in jetons[:PIECES_MAX]:
            if jeton.startswith("doc:"):
                piece = self._piece_de_docs(db, member, jeton) if db is not None else None
                if piece is None:
                    continue
                if isinstance(piece, str):
                    blocs.append({"type": "text", "text": piece})
                    continue
                nom, contenu = piece
            else:
                piece = self.pieces.pop(jeton, None)
                if piece is None or piece[0] != member.org_id or piece[1] != member.person_id:
                    continue
                _, _, nom, contenu = piece
            mime = guess_mime(nom)
            with tempfile.TemporaryDirectory(prefix="piece-") as dossier:
                chemin = Path(dossier) / "piece"
                chemin.write_bytes(contenu)
                blocs += [
                    {**b, "text": b["text"].replace("Fichier « ", "Fichier joint « ", 1)} if b.get("type") == "text" else b
                    for b in contenu_pour_claude(chemin, nom, mime)
                ]
            if nom.lower().endswith(POUR_L_ORDINATEUR):
                try:
                    envoye = self._claude().files.upload(file=(nom, contenu, mime))
                    blocs.append({"type": "container_upload", "file_id": envoye.id})
                    blocs.append({"type": "text", "text": f"(« {nom} » est aussi copié dans ton ordinateur.)"})
                except anthropic.APIError:
                    logger.exception("Copie de la pièce jointe vers l'ordinateur impossible")
        return blocs

    def ajouter_produit(self, db, member: Member, jeton: str, espace: str, dossier_id: int | None) -> dict:
        """« Faire » sur une carte de fichier fabriqué : il entre dans Docs,
        avec les droits de la personne (comme un import)."""
        produit = self.produits.get(jeton)
        if produit is None or produit[0] != member.org_id or produit[1] != member.person_id:
            raise DocError(404, "Ce fichier n'est plus disponible : redemandez-le à l'assistant.")
        _, _, nom, contenu = produit
        cree = self.documents.upload(db, member, espace, dossier_id, nom, io.BytesIO(contenu))
        self.produits.pop(jeton, None)
        return cree

    # ------------------------------------------------------------------
    # Un tour de conversation, en flux (Server-Sent Events)
    # ------------------------------------------------------------------

    def repondre(
        self, db, member: Member, conv: Conversation, texte: str, contexte: dict, modele: str = MODELE, compte=None,
        pieces: list[str] | None = None,
    ) -> Iterator[str]:
        """`db` : la session de la requête, ouverte jusqu'à la fin du flux
        (FastAPI ferme les dépendances après l'envoi de la réponse)."""
        if not self.actif:
            yield _evenement(type="erreur", message="L'assistant n'est pas configuré sur ce serveur.")
            return
        if not conv.verrou.acquire(blocking=False):
            yield _evenement(type="erreur", message="Une réponse est déjà en cours dans cette conversation.")
            return
        try:
            yield _evenement(type="conversation", id=conv.id)
            conv.messages.append({
                "role": "user",
                "content": [
                    *self._blocs_pieces(member, pieces or [], db),
                    {"type": "text", "text": self._contexte(db, member, contexte) + "\n\n" + texte},
                ],
            })
            modele = modele if modele in MODELES else MODELE
            cout = 0.0
            nb_appels, entree, sortie = 0, 0, 0
            deja_ecrit = False
            for _ in range(TOURS_MAX):
                reponse = None
                debut_appel = True
                for genre, valeur in self._un_appel(conv, modele):
                    if genre == "texte":
                        # Nouvel appel après des outils : nouveau paragraphe.
                        if debut_appel and deja_ecrit:
                            valeur = "\n\n" + valeur
                        debut_appel = False
                        deja_ecrit = True
                        yield _evenement(type="texte", texte=valeur)
                    elif genre == "outil":
                        yield _evenement(type="outil", nom=valeur)
                    else:
                        reponse = valeur
                cout += cout_usd(reponse.model, reponse.usage)
                nb_appels += 1
                entree += reponse.usage.input_tokens + (getattr(reponse.usage, "cache_read_input_tokens", 0) or 0)
                sortie += reponse.usage.output_tokens
                conv.messages.append({"role": "assistant", "content": [b.model_dump(exclude_none=True) for b in reponse.content]})
                conteneur = getattr(reponse, "container", None)
                if conteneur is not None and getattr(conteneur, "id", None):
                    conv.container_id = conteneur.id
                for carte in self._fichiers_produits(member, reponse, contexte):
                    yield _evenement(type="action", **carte)
                appels = [b for b in reponse.content if b.type == "tool_use"]
                if reponse.stop_reason == "refusal":
                    yield _evenement(type="texte", texte="\n\nJe ne peux pas répondre à cette demande.")
                    break
                if reponse.stop_reason == "pause_turn":
                    # L'ordinateur a travaillé longtemps : on relance la suite.
                    continue
                if not appels:
                    break
                if reponse.stop_reason == "max_tokens":
                    yield _evenement(type="erreur", message="Réponse trop longue, interrompue.")
                    break
                resultats = []
                copies = []
                for appel in appels:
                    yield _evenement(type="outil", nom=appel.name)
                    try:
                        if not isinstance(appel.input, dict):
                            raise ValueError("paramètres illisibles")
                        contenu, carte = self._executer(db, member, appel.name, appel.input, compte)
                        if carte is not None:
                            yield _evenement(type="action", **carte)
                        if isinstance(contenu, str) and contenu.startswith("COPIE:"):
                            _, file_id, nom_copie = contenu.split(":", 2)
                            copies.append({"type": "container_upload", "file_id": file_id})
                            contenu = f"« {nom_copie} » est copié dans ton ordinateur."
                        resultats.append({"type": "tool_result", "tool_use_id": appel.id, "content": contenu})
                    except anthropic.APIError as erreur:
                        logger.exception("Copie vers l'ordinateur impossible")
                        resultats.append({"type": "tool_result", "tool_use_id": appel.id, "is_error": True,
                                          "content": f"Copie impossible : {erreur.__class__.__name__}"})
                    except (DocError, KeyError, TypeError, ValueError) as erreur:
                        message = getattr(erreur, "message", None) or str(erreur)
                        resultats.append({"type": "tool_result", "tool_use_id": appel.id, "is_error": True, "content": message})
                conv.messages.append({"role": "user", "content": resultats + copies})
            conv.cout_usd += cout
            tour = {
                "question": texte[:120],
                "modele": MODELES[modele],
                "appels": nb_appels,
                "jetons_entree": entree,
                "jetons_sortie": sortie,
                "cout_usd": round(cout, 5),
            }
            conv.tours.append(tour)
            if self.noter_cout is not None and cout > 0:
                self.noter_cout(db, member.org_id, cout, f"{MODELES[modele]} : {texte[:150]}")
            logger.info("Assistant : conversation %s, %s, tour à %.4f $ (total %.4f $)", conv.id, modele, cout, conv.cout_usd)
            saison = self.cout_saison(db, member.org_id) if self.cout_saison is not None else None
            yield _evenement(
                type="fin", cout_usd=round(cout, 5), cout_total_usd=round(conv.cout_usd, 5), cout_saison_usd=saison, tour=tour
            )
        except AssistantIndisponible as erreur:
            yield _evenement(type="erreur", message=str(erreur))
        finally:
            conv.verrou.release()

    def _un_appel(self, conv: Conversation, modele: str = MODELE) -> Iterator[tuple[str, object]]:
        """Un appel à Claude, en flux : ("texte", morceau) et ("outil", nom)
        au fil de l'eau, puis ("fin", message final). Changer de modèle en cours de conversation est
        possible : les blocs de réflexion d'un autre modèle sont ignorés."""
        options = {}
        if modele != "claude-haiku-5-5":
            # Si le modèle décline la demande, l'API la rejoue sur le modèle
            # de repli qu'Anthropic recommande (pas de repli pour Haiku).
            options = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
        if conv.container_id:
            options["container"] = conv.container_id
        try:
            with self._claude().beta.messages.stream(
                model=modele,
                max_tokens=32000,
                system=CONSIGNE,
                tools=OUTILS,
                messages=conv.messages,
                output_config={"effort": "medium"},
                cache_control={"type": "ephemeral"},
                **options,
            ) as flux:
                for evenement in flux:
                    if evenement.type == "text":
                        yield "texte", evenement.text
                    elif evenement.type == "content_block_start" and getattr(evenement.content_block, "type", "") == "server_tool_use":
                        yield "outil", getattr(evenement.content_block, "name", "") or "code_execution"
                yield "fin", flux.get_final_message()
        except anthropic.AuthenticationError as erreur:
            logger.exception("Clé Anthropic refusée")
            raise AssistantIndisponible("La clé de l'API Claude est refusée.") from erreur
        except anthropic.RateLimitError as erreur:
            raise AssistantIndisponible("Trop de demandes en même temps : réessayez dans une minute.") from erreur
        except anthropic.BadRequestError as erreur:
            logger.exception("Demande refusée par l'API")
            raise AssistantIndisponible(f"Demande refusée : {erreur.message}") from erreur
        except anthropic.APIStatusError as erreur:
            logger.exception("Erreur de l'API Claude (%s)", erreur.status_code)
            raise AssistantIndisponible("L'assistant est indisponible : réessayez plus tard.") from erreur
        except anthropic.APIConnectionError as erreur:
            raise AssistantIndisponible("L'assistant est injoignable : réessayez plus tard.") from erreur
        except ValueError as erreur:
            # Paramètres d'outil illisibles (saisie en flux) : on s'arrête là.
            raise AssistantIndisponible("Réponse illisible, reformulez votre demande.") from erreur
