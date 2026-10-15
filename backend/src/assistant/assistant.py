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

import json
import logging
import os
import threading
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field

import anthropic
from documents.ports import Member
from documents.service import DocError, Documents

from .lecture import contenu_pour_claude

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

CONSIGNE = """Tu es l'assistant de l'onglet « Docs » d'une appli d'école de danse (une \
association). Tu aides la personne à retrouver, lire, résumer et ranger les dossiers et \
fichiers de l'école.

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
pour comprendre « ce dossier » ou « ce fichier »."""


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
]


class AssistantIndisponible(Exception):
    """Message lisible, montré tel quel."""


def cout_usd(modele: str, usage) -> float:
    entree, sortie, cache = PRIX.get(modele, PRIX[MODELE])
    lu = getattr(usage, "cache_read_input_tokens", 0) or 0
    ecrit = getattr(usage, "cache_creation_input_tokens", 0) or 0
    return (usage.input_tokens * entree + ecrit * entree * 1.25 + lu * cache + usage.output_tokens * sortie) / 1e6


@dataclass
class Conversation:
    id: str
    org_id: int
    person_id: int
    messages: list = field(default_factory=list)
    cout_usd: float = 0.0
    # Une ligne par question : modèle, nombre d'appels, jetons, coût.
    tours: list = field(default_factory=list)
    verrou: threading.Lock = field(default_factory=threading.Lock)


def _evenement(**donnees) -> str:
    return f"data: {json.dumps(donnees, ensure_ascii=False)}\n\n"


class Assistant:
    def __init__(self, documents: Documents, client: anthropic.Anthropic | None = None) -> None:
        self.documents = documents
        self._client = client
        self.conversations: dict[str, Conversation] = {}

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
        for issue in contexte.get("actions") or []:
            lignes.append(f"Suite à ta proposition : {str(issue)[:300]}")
        return "\n".join(lignes)

    # ------------------------------------------------------------------
    # Outils
    # ------------------------------------------------------------------

    @staticmethod
    def _ligne(e: dict) -> str:
        if e["kind"] == "folder":
            return f"- [dossier] {e['name']} (id {e['id']}, {e.get('child_count') or 0} éléments)"
        date = (e.get("updated_at") or "")[:10]
        auteur = f", par {e['updated_by']}" if e.get("updated_by") else ""
        return f"- [fichier] {e['name']} (id {e['id']}, {(e.get('size') or 0) // 1024} Ko, modifié le {date}{auteur})"

    def _executer(self, db, member: Member, nom: str, args: dict) -> tuple[list[dict] | str, dict | None]:
        """(résultat pour Claude, éventuelle carte d'action pour l'écran)."""
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
        if nom == "lire_fichier":
            chemin, nom_fichier, mime = d.content(db, member, args["fichier_id"])
            return contenu_pour_claude(chemin, nom_fichier, mime), None
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

    # ------------------------------------------------------------------
    # Un tour de conversation, en flux (Server-Sent Events)
    # ------------------------------------------------------------------

    def repondre(
        self, db, member: Member, conv: Conversation, texte: str, contexte: dict, modele: str = MODELE
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
            conv.messages.append(
                {"role": "user", "content": [{"type": "text", "text": self._contexte(db, member, contexte) + "\n\n" + texte}]}
            )
            modele = modele if modele in MODELES else MODELE
            cout = 0.0
            nb_appels, entree, sortie = 0, 0, 0
            deja_ecrit = False
            for _ in range(TOURS_MAX):
                reponse = None
                debut_appel = True
                for morceau, fin in self._un_appel(conv, modele):
                    if fin is None:
                        # Nouvel appel après des outils : nouveau paragraphe.
                        if debut_appel and deja_ecrit:
                            morceau = "\n\n" + morceau
                        debut_appel = False
                        deja_ecrit = True
                        yield _evenement(type="texte", texte=morceau)
                    else:
                        reponse = fin
                cout += cout_usd(reponse.model, reponse.usage)
                nb_appels += 1
                entree += reponse.usage.input_tokens + (getattr(reponse.usage, "cache_read_input_tokens", 0) or 0)
                sortie += reponse.usage.output_tokens
                conv.messages.append({"role": "assistant", "content": [b.model_dump(exclude_none=True) for b in reponse.content]})
                appels = [b for b in reponse.content if b.type == "tool_use"]
                if reponse.stop_reason == "refusal":
                    yield _evenement(type="texte", texte="\n\nJe ne peux pas répondre à cette demande.")
                    break
                if not appels:
                    break
                if reponse.stop_reason == "max_tokens":
                    yield _evenement(type="erreur", message="Réponse trop longue, interrompue.")
                    break
                resultats = []
                for appel in appels:
                    yield _evenement(type="outil", nom=appel.name)
                    try:
                        if not isinstance(appel.input, dict):
                            raise ValueError("paramètres illisibles")
                        contenu, carte = self._executer(db, member, appel.name, appel.input)
                        if carte is not None:
                            yield _evenement(type="action", **carte)
                        resultats.append({"type": "tool_result", "tool_use_id": appel.id, "content": contenu})
                    except (DocError, KeyError, TypeError, ValueError) as erreur:
                        message = getattr(erreur, "message", None) or str(erreur)
                        resultats.append({"type": "tool_result", "tool_use_id": appel.id, "is_error": True, "content": message})
                conv.messages.append({"role": "user", "content": resultats})
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
            logger.info("Assistant : conversation %s, %s, tour à %.4f $ (total %.4f $)", conv.id, modele, cout, conv.cout_usd)
            yield _evenement(type="fin", cout_usd=round(cout, 5), cout_total_usd=round(conv.cout_usd, 5), tour=tour)
        except AssistantIndisponible as erreur:
            yield _evenement(type="erreur", message=str(erreur))
        finally:
            conv.verrou.release()

    def _un_appel(self, conv: Conversation, modele: str = MODELE) -> Iterator[tuple[str, object]]:
        """Un appel à Claude, en flux : (texte, None) au fil de l'eau, puis
        ("", message final). Changer de modèle en cours de conversation est
        possible : les blocs de réflexion d'un autre modèle sont ignorés."""
        options = {}
        if modele != "claude-haiku-5-5":
            # Si le modèle décline la demande, l'API la rejoue sur le modèle
            # de repli qu'Anthropic recommande (pas de repli pour Haiku).
            options = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
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
                        yield evenement.text, None
                yield "", flux.get_final_message()
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
