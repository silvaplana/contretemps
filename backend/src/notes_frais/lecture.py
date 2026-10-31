"""Lecture d'un ticket de caisse ou d'une facture par Claude (spec
notes-de-frais.md §12), sur le modèle de inscriptions/lecture_fiche.py :
l'image part à l'API d'Anthropic, qui renvoie date, montant, commerçant,
catégorie et description. La personne relit et corrige avant d'enregistrer.

Sans clé (`ANTHROPIC_API_KEY`), la lecture est indisponible et le
formulaire se remplit à la main.
"""

from __future__ import annotations

import base64
import logging
import os
from collections.abc import Callable

import anthropic
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .ports import LectureImpossible, TicketLu

logger = logging.getLogger(__name__)

MODELE = "claude-opus-5-5"
PRIX_PAR_MODELE = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-opus-4-8": (5.0, 25.0),
}
TYPE_PDF = "application/pdf"
TYPES_IMAGE_API = {"image/jpeg", "image/png", "image/webp", "image/gif"}

CONSIGNE = """Tu lis une pièce comptable d'une association (ticket de caisse, facture, reçu, \
avis d'échéance, note d'honoraires, ou la preuve d'un virement : ordre de virement, avis \
d'opération, mail de la banque « virement exécuté »), photographiée ou fournie par le \
trésorier, pour pré-remplir l'application. Il relira et corrigera.

Règles :
- Recopie ce qui est écrit, sans rien inventer. Ce qui est illisible ou absent vaut null.
- `sorte` : « facture » pour tout ce qui réclame ou prouve une dépense (facture, reçu, ticket, \
avis d'échéance, justificatif de paiement d'un commerçant) ; « virement » pour la preuve d'un \
virement bancaire fait par l'association ; « autre » sinon.
- `date` : date de la pièce (achat, facture, ou exécution du virement), au format AAAA-MM-JJ. \
Les dates sont écrites à la française (jour/mois/année). Si le nom du fichier donne une date \
plus plausible que celle lue (année incohérente), prends celle du fichier.
- `montant_ttc` : le total payé ou viré, TTC, en euros (nombre décimal, ex. 48.9). Jamais un \
sous-total, une TVA ou un montant rendu.
- `commercant` : qui a émis la pièce : l'enseigne, la société, ou le nom de la personne \
(prénom et nom) pour une facture d'auto-entrepreneur ; pour un virement, la banque ou null.
- `emetteur_personne` : true si l'émetteur est une personne physique (auto-entrepreneur : \
« dispensé d'immatriculation », SIRET personnel, « TVA non applicable, art. 293 B »), false si \
c'est une société ou une enseigne, null si on ne sait pas.
- `client` : à qui la pièce est adressée (nom de la personne ou de l'association facturée, \
« Mme Julia Dho », « Association Contretemps ») ; null si absent.
- `beneficiaire`, `iban`, `motif` : pour un virement seulement, le nom du bénéficiaire, son \
IBAN (sans espaces) et le motif ou libellé ; null sinon.
- `categorie` : exactement un des libellés de la liste donnée, celui qui convient le mieux ; \
null si aucun ne convient.
- `description` : quelques mots en français qui disent ce qui a été acheté ou payé \
(ex. « Tissu pour costumes », « Cours de danse octobre 2025 »), sans le montant."""


class TicketJson(BaseModel):
    sorte: str | None
    date: str | None
    montant_ttc: float | None
    commercant: str | None
    emetteur_personne: bool | None
    client: str | None
    beneficiaire: str | None
    iban: str | None
    motif: str | None
    categorie: str | None
    description: str | None


def cout_usd(modele: str, jetons_entree: int, jetons_sortie: int) -> float:
    entree, sortie = PRIX_PAR_MODELE.get(modele, PRIX_PAR_MODELE[MODELE])
    return round((jetons_entree * entree + jetons_sortie * sortie) / 1_000_000, 4)


class LecteurClaude:
    def __init__(
        self,
        noter_cout: Callable[[Session, int, float, str], None] | None = None,
        plafond_atteint: Callable[[Session, int], bool] | None = None,
        client: anthropic.Anthropic | None = None,
    ) -> None:
        self.noter_cout = noter_cout
        self.plafond_atteint = plafond_atteint
        self._client = client

    @property
    def actif(self) -> bool:
        return self._client is not None or bool(os.environ.get("ANTHROPIC_API_KEY"))

    def _obtenir_client(self) -> anthropic.Anthropic:
        if self._client is None:
            self._client = anthropic.Anthropic()
        return self._client

    def lire(self, db: Session, org_id: int, contenu: bytes, type_mime: str, categories: list[str], nom: str = "") -> TicketLu:
        if type_mime != TYPE_PDF and type_mime not in TYPES_IMAGE_API:
            raise LectureImpossible("Ce format de photo ne peut pas être lu : remplissez à la main.")
        if self.plafond_atteint is not None and self.plafond_atteint(db, org_id):
            raise LectureImpossible("Le plafond mensuel d'IA de l'association est atteint : remplissez à la main.")
        source = {"type": "base64", "media_type": type_mime, "data": base64.standard_b64encode(contenu).decode("ascii")}
        bloc = {"type": "document" if type_mime == TYPE_PDF else "image", "source": source}
        liste = "\n".join(f"- {c}" for c in categories)
        texte = f"Catégories :\n{liste}" + (f"\n\nNom du fichier (indice, pas une vérité) : {nom}" if nom else "")
        try:
            reponse = self._obtenir_client().beta.messages.parse(
                model=MODELE,
                max_tokens=4000,
                system=CONSIGNE,
                messages=[{"role": "user", "content": [bloc, {"type": "text", "text": texte}]}],
                output_config={"effort": "low"},
                output_format=TicketJson,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.RateLimitError as erreur:
            raise LectureImpossible("Trop de lectures en même temps : réessayez dans une minute.") from erreur
        except anthropic.APIStatusError as erreur:
            logger.exception("Lecture de ticket refusée par l'API (%s)", erreur.status_code)
            raise LectureImpossible("Le ticket n'a pas pu être lu : remplissez à la main.") from erreur
        except anthropic.APIConnectionError as erreur:
            raise LectureImpossible("Le service de lecture est injoignable : remplissez à la main.") from erreur

        if self.noter_cout is not None:
            self.noter_cout(
                db, org_id, cout_usd(reponse.model, reponse.usage.input_tokens, reponse.usage.output_tokens), reponse.model
            )
        lu = reponse.parsed_output
        if reponse.stop_reason == "refusal" or lu is None:
            raise LectureImpossible("Le ticket n'a pas pu être lu : reprenez la photo bien à plat, ou remplissez à la main.")
        montant = round(lu.montant_ttc * 100) if lu.montant_ttc is not None else None
        return TicketLu(
            date=lu.date, montant_centimes=montant, commercant=lu.commercant, categorie=lu.categorie, description=lu.description,
            sorte=lu.sorte if lu.sorte in ("facture", "virement", "autre") else "facture",
            emetteur_personne=lu.emetteur_personne, client=lu.client,
            beneficiaire=lu.beneficiaire, iban=lu.iban, motif=lu.motif,
        )
