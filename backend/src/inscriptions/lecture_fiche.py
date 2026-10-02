"""Lecture d'une fiche d'inscription papier, remplie à la main, par Claude
(voir spec/SPEC-inscription.md : « Ajouter élève (OCR) »). Les photos du
recto et du verso partent à l'API d'Anthropic, qui renvoie les champs du
formulaire en ligne (voir schemas.py:InscriptionCreation) : l'admin les
corrige ensuite dans CE formulaire, rien n'est enregistré ici.

Sans clé (`ANTHROPIC_API_KEY`, voir .env.example), la lecture est
simplement indisponible : le reste de l'appli n'en dépend pas.
"""

from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass

import anthropic
from pydantic import BaseModel

logger = logging.getLogger(__name__)

MODELE = "claude-opus-5-5"

# Prix en dollars par million de jetons (entrée, sortie), pour annoncer à
# l'admin ce qu'a coûté la lecture. Les modèles de repli ne servent que si
# le premier décline la demande.
PRIX_PAR_MODELE = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-opus-4-8": (5.0, 25.0),
}

TYPES_IMAGE = {"image/jpeg", "image/png", "image/webp", "image/gif"}
TYPE_PDF = "application/pdf"

CONSIGNE = """Tu lis une fiche d'inscription d'une école de danse, remplie à la main, \
photographiée en une ou deux pages (recto : informations de l'élève ; verso : droit à \
l'image et attestation du règlement intérieur). Tu en extrais les champs demandés pour \
pré-remplir un formulaire qu'un administrateur de l'école relira et corrigera.

Règles :
- Recopie ce qui est écrit, sans rien inventer. Un champ vide ou absent de la photo vaut null.
- Un champ que tu as dû deviner (écriture difficile, rature, photo floue ou coupée) est \
rempli avec ta meilleure lecture ET son nom est ajouté à `champs_douteux`. L'administrateur \
vérifiera ces champs en priorité : mieux vaut en signaler un de trop qu'un de moins. Les \
emails et les numéros de téléphone méritent une attention particulière, une seule lettre \
ou un seul chiffre faux les rend inutilisables.
- `eleve_date_naissance` au format AAAA-MM-JJ. Les dates sont écrites à la française \
(jour/mois/année).
- Noms de famille en majuscules, prénoms avec une majuscule initiale. Téléphones français \
en « 06 12 34 56 78 ».
- « Nom / Prénom » de la personne à prévenir : sépare le nom et le prénom.
- `cours_ids` : la fiche ne nomme pas les cours, elle coche des disciplines (Classique, \
Jazz, Contemporain, Street, Éveil) et un niveau (Éveil, Initiation, Moyen, Junior, \
Intermédiaire, Avancé). Choisis dans la liste des cours de l'école, donnée plus bas, ceux \
qui correspondent à chaque discipline cochée au niveau coché, et renvoie leurs numéros. \
Les noms de cours sont abrégés (« Class Moy » : Classique Moyen ; « Contempo » : \
Contemporain ; « AV » : Avancé ; « Ini » : Initiation ; « Inter » : Intermédiaire). \
N'ajoute jamais un cours qui n'est pas dans la liste. Si une combinaison n'existe pas, si \
plusieurs niveaux sont cochés, ou si le « nombre de cours / semaine » écrit ne correspond \
pas au nombre de cours trouvés, ajoute `cours_ids` à `champs_douteux` et explique-le dans \
`remarques`.
- Droit à l'image : trois cases (site internet, réseaux sociaux, affiches). Une case \
cochée vaut autorisation pour cet usage : dès qu'au moins une case est cochée, \
`droit_image_autorise` est vrai, même si la mention « J'autorise / Je n'autorise pas » \
n'est pas rayée. Il est faux si aucune case n'est cochée, ou si « J'autorise » est rayé. \
Si des cases sont cochées ALORS QUE « J'autorise » est rayé, c'est contradictoire : \
faux, et le champ est douteux.
- `reglement_signe` est vrai si l'attestation du règlement intérieur porte une signature \
ou la mention « Lu et approuvé ». `signataire_nom` est le nom écrit après \
« Je soussigné(e) ».
- `famille_membres` : 2 si la fiche porte la mention manuscrite « Famille 2 » ou \
« Famille 2 membres », 3 pour « Famille 3 » ou « Famille 3 membres » (réduction accordée aux \
familles qui inscrivent plusieurs membres ; la mention peut être écrite n'importe où sur la \
fiche). Sans cette mention, 1.
- `remarques` : une ou deux phrases courtes, en français, pour l'administrateur, seulement \
s'il y a quelque chose à lui signaler (page manquante, photo illisible, incohérence). \
Sinon null."""


class FicheLue(BaseModel):
    """Ce que le modèle renvoie : les champs du formulaire en ligne, plus
    ce qu'il faut relire."""

    eleve_nom: str | None
    eleve_prenom: str | None
    eleve_date_naissance: str | None
    eleve_adresse: str | None
    eleve_telephone: str | None
    eleve_email: str | None
    contact_urgence_nom: str | None
    contact_urgence_prenom: str | None
    contact_urgence_lien: str | None
    contact_urgence_telephone: str | None
    cours_ids: list[int]
    allergies: str | None
    traitement_medical: str | None
    informations_importantes: str | None
    droit_image_autorise: bool
    droit_image_site: bool
    droit_image_reseaux: bool
    droit_image_affiches: bool
    reglement_signe: bool
    signataire_nom: str | None
    famille_membres: int
    champs_douteux: list[str]
    remarques: str | None


@dataclass(frozen=True)
class Page:
    contenu: bytes
    type_mime: str


@dataclass(frozen=True)
class ResultatLecture:
    fiche: FicheLue
    modele: str
    jetons_entree: int
    jetons_sortie: int
    cout_usd: float


class LectureIndisponible(Exception):
    """La lecture n'a pas pu avoir lieu ; le message est montrable à l'admin."""


def cout_usd(modele: str, jetons_entree: int, jetons_sortie: int) -> float:
    entree, sortie = PRIX_PAR_MODELE.get(modele, PRIX_PAR_MODELE[MODELE])
    return round((jetons_entree * entree + jetons_sortie * sortie) / 1_000_000, 4)


def _bloc(page: Page) -> dict:
    source = {
        "type": "base64",
        "media_type": page.type_mime,
        "data": base64.standard_b64encode(page.contenu).decode("ascii"),
    }
    return {"type": "document" if page.type_mime == TYPE_PDF else "image", "source": source}


class LectureFiche:
    def __init__(self, client: anthropic.Anthropic | None = None) -> None:
        self._client = client

    @property
    def actif(self) -> bool:
        return self._client is not None or bool(os.environ.get("ANTHROPIC_API_KEY"))

    def _obtenir_client(self) -> anthropic.Anthropic:
        if self._client is None:
            self._client = anthropic.Anthropic()
        return self._client

    def lire(self, pages: list[Page], cours: list[tuple[int, str]]) -> ResultatLecture:
        """`cours` : (numéro, nom) des cours de l'école, parmi lesquels le
        modèle choisit."""
        if not self.actif:
            raise LectureIndisponible("La lecture automatique des fiches n'est pas configurée.")
        liste_cours = "\n".join(f"- {cours_id} : {nom}" for cours_id, nom in cours)
        contenu = [_bloc(page) for page in pages]
        contenu.append({"type": "text", "text": f"Cours de l'école (numéro : nom) :\n{liste_cours}"})
        try:
            reponse = self._obtenir_client().beta.messages.parse(
                model=MODELE,
                max_tokens=16000,
                system=CONSIGNE,
                messages=[{"role": "user", "content": contenu}],
                output_config={"effort": "medium"},
                output_format=FicheLue,
                # Si le modèle décline la demande, l'API la rejoue sur le
                # modèle de repli qu'Anthropic recommande.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.AuthenticationError as erreur:
            logger.exception("Clé Anthropic refusée")
            raise LectureIndisponible("La clé de l'API Claude est refusée.") from erreur
        except anthropic.RateLimitError as erreur:
            raise LectureIndisponible("Trop de lectures en même temps : réessayez dans une minute.") from erreur
        except anthropic.BadRequestError as erreur:
            logger.exception("Lecture de fiche refusée par l'API")
            raise LectureIndisponible(f"La fiche n'a pas pu être lue : {erreur.message}") from erreur
        except anthropic.APIStatusError as erreur:
            logger.exception("Erreur de l'API Claude (%s)", erreur.status_code)
            raise LectureIndisponible("Le service de lecture est indisponible : réessayez plus tard.") from erreur
        except anthropic.APIConnectionError as erreur:
            raise LectureIndisponible("Le service de lecture est injoignable : réessayez plus tard.") from erreur

        if reponse.stop_reason == "refusal" or reponse.parsed_output is None:
            logger.warning("Lecture de fiche sans résultat (%s)", reponse.stop_reason)
            raise LectureIndisponible("La fiche n'a pas pu être lue. Reprenez les photos, bien à plat et nettes.")

        entree = reponse.usage.input_tokens
        sortie = reponse.usage.output_tokens
        return ResultatLecture(
            fiche=reponse.parsed_output,
            modele=reponse.model,
            jetons_entree=entree,
            jetons_sortie=sortie,
            cout_usd=cout_usd(reponse.model, entree, sortie),
        )
