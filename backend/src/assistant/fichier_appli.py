"""L'assistant dans un fichier de l'appli (spec fichier-de-base.md §2.1) :
le même chat que dans Docs, qui sait quel fichier est ouvert et peut écrire
ses deux formulaires.

Le chat et BlockNote modifient le même JSON de blocs : l'assistant lit la
version courante à chaque message (la personne a pu corriger à la main) et
renvoie des formulaires entiers, contrôlés par le serveur comme une
modification à la main. Chaque modification crée une version (origine
« ai ») ; l'écran la montre aussitôt, avec « Annuler ».
"""

from __future__ import annotations

import json
import uuid

from documents import assembly, minutes, signing
from documents.app_content import (
    ACT_TYPES,
    FAMILY_ENTRY_TYPES,
    LAYOUT_TYPES,
    QUESTION_TYPES,
    RESULT_TYPES,
)
from documents.models import DocNode
from documents.ports import Member
from documents.service import DocError, Documents

NATURES = {"inform": "Informer (à lire)", "question": "Questionner (des questions, réponses dans le fichier)",
           "act": "Agir (crée membres, inscriptions, paiements)"}
ETATS = {None: "Brouillon", "draft": "Brouillon", "validated": "Validé", "official": "Officiel"}
FORMULAIRES = {"entry": "le formulaire d'entrée", "result": "le formulaire de résultat"}

CONSIGNE_FICHIER = """

Fichiers de l'appli : ce sont des fichiers que l'on fabrique dans Contretemps (pas des PDF ni des \
Word). Chacun a une nature (Informer, Questionner, Agir) et deux formulaires : le « formulaire \
d'entrée » (la page que les gens reçoivent : texte et questions) et le « formulaire de résultat » \
(ce que l'on voit des réponses : compteur, graphique, total, tableau). Quand la personne a un \
tel fichier ouvert, le contexte te donne son contenu actuel en JSON : pars toujours de lui, elle a \
pu le corriger à la main. Pour le changer, appelle « modifier_fichier_appli » avec le ou les \
formulaires ENTIERS (tous les blocs, pas seulement les nouveaux) : la modification s'affiche \
aussitôt, avec « Annuler ». Le fichier doit être en Brouillon ; sinon, dis-lui de le repasser en \
Brouillon (bouton de l'état, en haut).

Format d'un bloc : {"id", "type", "props", "content", "children"}.
- Garde l'« id » des blocs existants (les réponses déjà reçues y sont rangées) ; pour un nouveau \
bloc, omets l'id.
- Texte (« content ») : liste de morceaux {"type": "text", "text": "…", "styles": {"bold": true}} \
ou {"type": "link", "href": "https://…", "content": [morceaux]}. Jamais de HTML.
- Mise en page : paragraph, heading (props.level 1 à 3), quote, bulletListItem, numberedListItem, \
checkListItem, divider (sans content).
- Questions (Questionner et Agir), sans « content », réglées par props : shortText, longText, date, \
number, yesNo, signature avec {"label": "La question", "required": true|false} ; choice avec en plus \
{"options": "Choix 1\\nChoix 2", "multiple": true|false}.
- Agir seulement : member {"label", "required"} (nom, prénom, email, téléphone, relié à la fiche \
du membre) et payment {"label", "amount": 25}.
- Formulaire de résultat (pas pour Informer) : texte, et responseCount, responseTable, \
choiceChart {"questionId": id d'une question choice ou yesNo}, total {"questionId": id d'une \
question number ou payment}. Vide = fabriqué tout seul à partir des questions.
Une image ou un lien joint sert d'inspiration : reprends la structure et les questions, en \
français, au nom de l'école ; jamais un chiffre inventé (montants, dates) : demande-les."""


BLOC = {"type": "object", "description": "Un bloc (voir le format dans la consigne)."}


OUTIL_FICHIER = {
    "name": "modifier_fichier_appli",
    "description": (
        "Remplace le formulaire d'entrée et/ou le formulaire de résultat d'un fichier de l'appli "
        "(en Brouillon). Donne chaque formulaire changé en entier ; null = inchangé."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "fichier_id": {"type": "integer", "description": "Numéro du fichier de l'appli."},
            "formulaire_entree": {
                "type": ["array", "null"], "items": BLOC,
                "description": "Tous les blocs du formulaire d'entrée, ou null.",
            },
            "formulaire_resultat": {
                "type": ["array", "null"], "items": BLOC,
                "description": "Tous les blocs du formulaire de résultat, ou null.",
            },
            "resume": {"type": "string", "description": "Ce qui change, en quelques mots (ex. « 3 questions ajoutées »)."},
        },
        "required": ["fichier_id", "formulaire_entree", "formulaire_resultat", "resume"],
    },
}


def _normaliser(blocs, profondeur: int = 0) -> list[dict]:
    """Complète ce que le modèle peut omettre : id des nouveaux blocs,
    props, content et children vides."""
    if not isinstance(blocs, list):
        raise DocError(422, "Un formulaire est une liste de blocs.")
    propres = []
    for bloc in blocs:
        if not isinstance(bloc, dict):
            raise DocError(422, "Bloc mal formé.")
        genre = bloc.get("type")
        sans_texte = genre in QUESTION_TYPES | ACT_TYPES | RESULT_TYPES or genre == "divider"
        contenu = bloc.get("content")
        if isinstance(contenu, str):
            contenu = [{"type": "text", "text": contenu, "styles": {}}]
        propres.append({
            "id": str(bloc.get("id") or uuid.uuid4()),
            "type": genre,
            "props": bloc.get("props") or {},
            "content": [] if sans_texte else (contenu or []),
            "children": _normaliser(bloc.get("children") or [], profondeur + 1) if profondeur < 3 else [],
        })
    return propres


class FichierAppli:
    def __init__(self, documents: Documents) -> None:
        self.documents = documents

    @property
    def apps(self):
        return self.documents.apps

    def contexte(self, db, member: Member, fichier_id: int, formulaire: str | None) -> str:
        f = self.apps.get(db, member, fichier_id)
        permis = sorted(FAMILY_ENTRY_TYPES[f["family"]] - LAYOUT_TYPES) if f["family"] in FAMILY_ENTRY_TYPES else []
        lignes = [(
            f"Elle a ouvert le fichier de l'appli « {f['name']} » (id {f['id']}), nature {NATURES.get(f['family'], f['family'])}, "
            f"état {ETATS.get(f['status'], f['status'])}, {f['response_count']} réponse(s) reçue(s)."
        )]
        if formulaire in FORMULAIRES:
            lignes.append(f"À l'écran : {FORMULAIRES[formulaire]}.")
        if not f["editable"]:
            lignes.append("Il n'est pas modifiable maintenant (pas en Brouillon, ou pas le droit).")
        lignes.append("Blocs de questions permis dans le formulaire d'entrée : " + (", ".join(permis) or "aucun (à lire seulement)") + ".")
        lignes.append("Contenu actuel : " + json.dumps(f["content"], ensure_ascii=False, separators=(",", ":")))
        return "\n".join(lignes)

    def lire(self, db, member: Member, fichier_id: int) -> str:
        f = self.apps.get(db, member, fichier_id)
        texte = (
            f"Fichier de l'appli « {f['name']} », nature {NATURES.get(f['family'], f['family'])}, "
            f"état {ETATS.get(f['status'], f['status'])} : "
            + json.dumps(f["content"], ensure_ascii=False, separators=(",", ":"))
        )
        # Convocation d'AG : où en sont les réponses, comme Résultats
        # (procurations.md §1.4), pour qui peut voir Résultats.
        if f["can_edit"] and assembly.block_of(f["content"]):
            node = db.get(DocNode, f["id"])
            texte += "\n\nRéponses à la convocation (chiffres de l'appli) :\n" + assembly.status_text(self.documents, db, node, f["content"])
        # Procès-verbal d'AG : où en sont les signatures (proces-verbal-ag.md §4).
        if f["can_edit"] and minutes.block_of(f["content"]):
            texte += "\n\nSignatures du procès-verbal (état de l'appli) : " + minutes.status_text(self.documents, db, db.get(DocNode, f["id"]))
        # Document à signer : où en sont les signatures (signature-documents.md §5).
        if f["can_edit"] and signing.block_of(f["content"]):
            texte += "\n\nSignatures du document (état de l'appli) : " + signing.status_text(self.documents, db, db.get(DocNode, f["id"]))
        return texte

    def modifier(self, db, member: Member, args: dict) -> tuple[str, dict]:
        entree, resultat = args.get("formulaire_entree"), args.get("formulaire_resultat")
        if entree is None and resultat is None:
            raise DocError(422, "Rien à modifier : donne au moins un formulaire.")
        f = self.apps.get(db, member, int(args["fichier_id"]))
        if not f["editable"]:
            raise DocError(409, "Ce fichier n'est pas modifiable : il faut qu'il soit en Brouillon et que la personne ait le droit de le modifier.")
        avant = f["content"]
        apres = {
            "schema": avant.get("schema", 1),
            "entry": {"blocks": _normaliser(entree) if entree is not None else avant["entry"]["blocks"]},
            "result": {"blocks": _normaliser(resultat) if resultat is not None else avant["result"]["blocks"]},
        }
        base = f["version"]["number"] if f["version"] else None
        enregistre = self.apps.save(db, member, f["id"], apres, base_version=base, origin="ai")
        resume = str(args.get("resume") or "Fichier modifié")[:200]
        carte = {
            "id": uuid.uuid4().hex[:12],
            "kind": "fichier_modifie",
            "etat": "faite",
            "fichier_id": f["id"],
            "version": enregistre["version"]["number"],
            "content": apres,
            "avant": avant,
            "libelle": f"« {f['name']} » : {resume}",
        }
        return f"Enregistré (version {enregistre['version']['number']}), affiché à la personne avec « Annuler ».", carte
