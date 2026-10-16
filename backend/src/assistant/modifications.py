"""Modifications des données de l'école proposées par l'assistant (Seb,
16 octobre) : élèves et inscriptions aux cours, paiements, présences et
heures des professeurs, cours, chorégraphies.

Rien n'est modifié sans la personne : l'assistant propose une liste de
changements (outil « proposer_modifications »), le serveur la vérifie et la
décrit lui-même avec les vrais noms et les valeurs actuelles, l'écran
l'affiche en une carte récapitulative (cases à décocher, « Tout faire » ou
« Annuler »), puis seuls les changements cochés sont faits, par les mêmes
services que les écrans de l'appli.

Réservé aux administrateurs et au Super User. Jamais les champs de santé."""

from __future__ import annotations

import datetime as dt
import logging
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from choregraphies.models import Choregraphie, choregraphies_eleves
from comptes import roles
from comptes.models import Compte
from cours.models import Cours, cours_professeurs, eleves_cours
from eleves.models import ContactEleve, ProfilEleve
from saisons.portee import SaisonEnLectureSeule
from sqlalchemy import select
from sqlalchemy.orm import Session

from .donnees import COLONNES_ROUGES, DonneesEcole

logger = logging.getLogger(__name__)

CHANGEMENTS_MAX = 100
EN_ATTENTE_MAX = 40

CHAMPS_ELEVE = {
    "nom": "nom", "prenom": "prénom", "email": "email", "telephone": "téléphone", "adresse": "adresse",
    "date_naissance": "date de naissance", "montant_total_annee": "montant de l'année",
    "montant_paye": "montant payé", "statut_paiement": "paiement",
    "commentaire_admin": "commentaire", "ligne_rouge": "en rouge", "cellules_rouges": "colonnes en rouge",
}
CHAMPS_COMPTE = ("nom", "prenom", "email", "telephone")
CHAMPS_CONTACT = {"nom": "nom", "prenom": "prénom", "lien": "lien", "telephone": "téléphone", "email": "email"}
CHAMPS_COURS = {
    "nom": "nom", "discipline": "discipline", "niveau": "niveau", "jour": "jour", "heure_debut": "début",
    "heure_fin": "fin", "salle": "salle", "descriptif": "descriptif",
}
CHAMPS_CHOREGRAPHIE = {"nom": "nom", "horaire_repetition": "répétition", "costume": "costume"}
STATUTS_PRESENCE = {"present": "présent", "absent": "absent", "retard": "en retard"}
STATUTS_PAIEMENT = {"en_cours": "en cours", "paye": "payé"}
HEURE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

TYPES = {
    "creer_eleve": "nouvel élève : nom, prenom, champs (facultatif), cours_ids (facultatif)",
    "modifier_eleve": "eleve_id, champs",
    "inscrire_cours": "eleve_id, cours_id",
    "retirer_cours": "eleve_id, cours_id",
    "ajouter_contact": "eleve_id, champs (nom, prenom, lien, telephone, email)",
    "modifier_contact": "contact_id, champs",
    "noter_paiement": "eleve_id, montant (en euros, ajouté au montant payé)",
    "presence_eleve": "cours_id, date, eleve_id, statut (present, absent, retard)",
    "heures_professeur": "cours_id, date, professeur_id, champs (heure_debut_reelle, heure_fin_reelle HH:MM, depassement_minutes)",
    "modifier_cours": "cours_id, champs",
    "ajouter_professeur_cours": "cours_id, professeur_id",
    "retirer_professeur_cours": "cours_id, professeur_id",
    "creer_choregraphie": "cours_id, champs (nom, horaire_repetition, costume), eleve_ids",
    "modifier_choregraphie": "choregraphie_id, champs, eleve_ids (facultatif : remplace la liste)",
}

_ENTIER = {"type": "integer"}
OUTIL_MODIFICATIONS = {
    "name": "proposer_modifications",
    "description": (
        "Propose des changements dans les données de l'école. Rien n'est fait tout de suite : la personne "
        "voit une carte récapitulative, décoche ce qu'elle ne veut pas, puis valide. Regroupe tous les "
        "changements d'une même demande dans un seul appel. Lis d'abord les données (numéros, valeurs "
        "actuelles) avec les outils de lecture. Types et paramètres : "
        + " ; ".join(f"{t} ({p})" for t, p in TYPES.items())
        + ". Champs d'un élève : " + ", ".join(CHAMPS_ELEVE) + " (statut_paiement : en_cours ou paye ; "
        "date_naissance : AAAA-MM-JJ ; commentaire_admin : le commentaire de l'administration, donne le texte "
        "complet, en gardant l'ancien si on ajoute ; ligne_rouge : true ou false, toute la ligne en rouge dans "
        "Admin > Élèves ; cellules_rouges : la liste complète des colonnes en rouge parmi "
        + ", ".join(COLONNES_ROUGES) + "). Champs d'un cours : " + ", ".join(CHAMPS_COURS)
        + ". Dates : AAAA-MM-JJ. Jamais les informations de santé."
    ),
    "eager_input_streaming": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "titre": {"type": "string", "description": "Titre court de la carte, ex. « Présences de l'Éveil du 14 octobre »."},
            "changements": {
                "type": "array",
                "maxItems": CHANGEMENTS_MAX,
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": list(TYPES)},
                        "eleve_id": _ENTIER, "cours_id": _ENTIER, "professeur_id": _ENTIER,
                        "choregraphie_id": _ENTIER, "contact_id": _ENTIER,
                        "nom": {"type": "string"}, "prenom": {"type": "string"},
                        "date": {"type": "string"}, "statut": {"type": "string"},
                        "montant": {"type": "number"},
                        "champs": {"type": "object"},
                        "eleve_ids": {"type": "array", "items": _ENTIER},
                        "cours_ids": {"type": "array", "items": _ENTIER},
                    },
                    "required": ["type"],
                },
            },
        },
        "required": ["titre", "changements"],
    },
}


class Refus(ValueError):
    """Changement refusé : message lisible, renvoyé à l'assistant."""


@dataclass
class Ligne:
    libelle: str
    faire: Callable[[Session], None]


def _nom(c: Compte) -> str:
    return f"{c.prenom} {c.nom}".strip()


def _valeur(v) -> str:
    if isinstance(v, bool):
        return "oui" if v else "non"
    if isinstance(v, list):
        return ", ".join(COLONNES_ROUGES.get(c, str(c)) for c in v) or "aucune"
    if v is None or v == "":
        return "vide"
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def _date(texte) -> dt.date:
    try:
        return dt.date.fromisoformat(str(texte))
    except ValueError as erreur:
        raise Refus(f"date illisible « {texte} » (AAAA-MM-JJ attendu)") from erreur


def _jour(date: dt.date) -> str:
    return date.strftime("%d/%m/%Y")


class Modifications:
    def __init__(self, *, eleves, comptes, cours, presence, choregraphies) -> None:
        self.eleves = eleves
        self.comptes = comptes
        self.cours = cours
        self.presence = presence
        self.choregraphies = choregraphies
        self.donnees = DonneesEcole()
        # jeton -> (org_id, person_id, ecole_id, [Ligne])
        self.attente: dict[str, tuple[int, int, int, list[Ligne]]] = {}

    # --- Proposer ------------------------------------------------------

    def proposer(self, db: Session, compte: Compte, ecole_id: int, person_id: int, args: dict) -> tuple[str, dict | None]:
        if not self.donnees.perimetre(db, compte, ecole_id).tout:
            return "Modifier les données de l'école est réservé aux administrateurs.", None
        changements = args.get("changements") or []
        if not isinstance(changements, list) or not changements:
            return "Aucun changement proposé.", None
        lignes, refus = [], []
        for numero, ch in enumerate(changements[:CHANGEMENTS_MAX], 1):
            try:
                if not isinstance(ch, dict):
                    raise Refus("changement illisible")
                methode = getattr(self, f"_{ch.get('type')}", None)
                if ch.get("type") not in TYPES or methode is None:
                    raise Refus(f"type inconnu « {ch.get('type')} »")
                lignes.append(methode(db, ecole_id, ch))
            except Refus as erreur:
                refus.append(f"n° {numero} : {erreur}")
        if not lignes:
            return "Rien à proposer. Refusés : " + " ; ".join(refus), None
        while len(self.attente) >= EN_ATTENTE_MAX:
            self.attente.pop(next(iter(self.attente)))
        jeton = uuid.uuid4().hex
        self.attente[jeton] = (ecole_id, person_id, ecole_id, lignes)
        titre = str(args.get("titre") or "Modifications").strip()[:120]
        carte = {
            "id": jeton[:12], "kind": "modifications", "jeton": jeton, "libelle": titre,
            "lignes": [ligne.libelle for ligne in lignes],
        }
        texte = (
            f"Proposé à la personne sur une carte récapitulative ({len(lignes)} changement(s)) : elle coche puis "
            "valide, rien n'est encore fait. Tu sauras au message suivant ce qui a été fait."
        )
        if refus:
            texte += " Refusés (non proposés) : " + " ; ".join(refus)
        return texte, carte

    def executer(self, db: Session, compte: Compte, ecole_id: int, person_id: int, jeton: str, indices: list[int]) -> list[dict]:
        attente = self.attente.get(jeton)
        if attente is None or attente[0] != ecole_id or attente[1] != person_id:
            raise Refus("Cette proposition n'est plus disponible : redemandez à l'assistant.")
        if not self.donnees.perimetre(db, compte, ecole_id).tout:
            raise Refus("Réservé aux administrateurs.")
        self.attente.pop(jeton)
        lignes = attente[3]
        resultats = []
        for i in sorted(set(indices)):
            if not 0 <= i < len(lignes):
                continue
            ligne = lignes[i]
            try:
                ligne.faire(db)
                db.commit()
                resultats.append({"index": i, "libelle": ligne.libelle, "ok": True})
            except Exception as erreur:  # chaque ligne à part : une erreur n'arrête pas les autres
                db.rollback()
                if isinstance(erreur, SaisonEnLectureSeule):
                    message = "saison terminée : lecture seule"
                elif isinstance(erreur, ValueError):
                    message = str(erreur) or "refusé"
                else:
                    logger.exception("Modification de l'assistant en échec")
                    message = "erreur inattendue"
                resultats.append({"index": i, "libelle": ligne.libelle, "ok": False, "erreur": message})
        return resultats

    # --- Lecture sûre (même école) -------------------------------------

    def _eleve(self, db: Session, ecole_id: int, eleve_id) -> Compte:
        e = db.get(Compte, eleve_id) if isinstance(eleve_id, int) else None
        if e is None or e.ecole_id != ecole_id or not roles.is_eleve(e):
            raise Refus(f"élève n° {eleve_id} introuvable")
        return e

    def _un_cours(self, db: Session, ecole_id: int, cours_id) -> Cours:
        c = db.get(Cours, cours_id) if isinstance(cours_id, int) else None
        if c is None or c.ecole_id != ecole_id:
            raise Refus(f"cours n° {cours_id} introuvable")
        return c

    def _prof(self, db: Session, ecole_id: int, prof_id) -> Compte:
        p = db.get(Compte, prof_id) if isinstance(prof_id, int) else None
        if p is None or p.ecole_id != ecole_id or not roles.is_prof(p):
            raise Refus(f"professeur n° {prof_id} introuvable")
        return p

    def _choregraphie(self, db: Session, ecole_id: int, choregraphie_id) -> tuple[Choregraphie, Cours]:
        ch = db.get(Choregraphie, choregraphie_id) if isinstance(choregraphie_id, int) else None
        cours = db.get(Cours, ch.cours_id) if ch else None
        if ch is None or cours is None or cours.ecole_id != ecole_id:
            raise Refus(f"chorégraphie n° {choregraphie_id} introuvable")
        return ch, cours

    @staticmethod
    def _champs(ch: dict, permis: dict, obligatoire: bool = True) -> dict:
        champs = ch.get("champs") or {}
        if not isinstance(champs, dict):
            raise Refus("champs illisibles")
        inconnus = [c for c in champs if c not in permis]
        if inconnus:
            raise Refus(f"champ non modifiable : {', '.join(inconnus)}")
        if obligatoire and not champs:
            raise Refus("aucun champ à changer")
        return champs

    @staticmethod
    def _champs_eleve(champs: dict) -> dict:
        propres = {}
        for cle, v in champs.items():
            if cle == "date_naissance":
                v = _date(v) if v else None
            elif cle in ("montant_total_annee", "montant_paye"):
                try:
                    v = float(v)
                except (TypeError, ValueError) as erreur:
                    raise Refus(f"montant illisible « {v} »") from erreur
                if v < 0:
                    raise Refus("montant négatif")
            elif cle == "ligne_rouge":
                if not isinstance(v, bool):
                    raise Refus("ligne_rouge : true ou false")
            elif cle == "cellules_rouges":
                if not isinstance(v, list) or any(c not in COLONNES_ROUGES for c in v):
                    raise Refus("cellules_rouges : liste de colonnes parmi " + ", ".join(COLONNES_ROUGES))
                v = list(dict.fromkeys(v))
            elif cle == "statut_paiement":
                if v not in STATUTS_PAIEMENT:
                    raise Refus("statut_paiement : en_cours ou paye")
            else:
                v = None if v is None else str(v).strip()
                if cle in ("nom", "prenom") and not v:
                    raise Refus(f"{CHAMPS_ELEVE[cle]} vide")
            propres[cle] = v
        return propres

    def _ecrire_eleve(self, db: Session, eleve_id: int, champs: dict) -> None:
        compte = {c: champs[c] for c in CHAMPS_COMPTE if c in champs}
        profil = {c: v for c, v in champs.items() if c not in CHAMPS_COMPTE}
        if compte:
            self.comptes.update(db, eleve_id, **compte)
        if profil:
            self.eleves.update_profil(db, eleve_id, **profil)

    @staticmethod
    def _actuel(db: Session, eleve: Compte, cle: str):
        if cle in CHAMPS_COMPTE:
            return getattr(eleve, cle)
        profil = db.scalar(select(ProfilEleve).where(ProfilEleve.compte_id == eleve.id))
        return getattr(profil, cle, None) if profil else None

    # --- Les changements -----------------------------------------------

    def _creer_eleve(self, db: Session, ecole_id: int, ch: dict) -> Ligne:
        nom, prenom = str(ch.get("nom") or "").strip(), str(ch.get("prenom") or "").strip()
        if not nom or not prenom:
            raise Refus("nom et prénom obligatoires")
        champs = self._champs_eleve(self._champs(ch, CHAMPS_ELEVE, obligatoire=False))
        cours = [self._un_cours(db, ecole_id, c) for c in ch.get("cours_ids") or []]
        details = [f"{CHAMPS_ELEVE[c]} {_valeur(v)}" for c, v in champs.items()]
        if cours:
            details.append("cours " + ", ".join(c.nom for c in cours))
        libelle = f"Nouvel élève : {prenom} {nom}" + (f" ({' ; '.join(details)})" if details else "")

        cours_ids = [c.id for c in cours]

        def faire(db: Session) -> None:
            compte, _ = self.eleves.create(db, ecole_id, nom=nom, prenom=prenom)
            nouveau_id = compte.id
            try:
                if champs:
                    self._ecrire_eleve(db, nouveau_id, champs)
                for cours_id in cours_ids:
                    self.cours.inscrire_eleve(db, cours_id, nouveau_id)
            except Exception as erreur:
                # La fiche est déjà enregistrée : on le dit, pour ne pas la recréer.
                logger.exception("Élève créé, suite en échec")
                raise ValueError(f"élève créé (n° {nouveau_id}), mais le reste n'a pas pu être fait") from erreur

        return Ligne(libelle, faire)

    def _modifier_eleve(self, db: Session, ecole_id: int, ch: dict) -> Ligne:
        eleve = self._eleve(db, ecole_id, ch.get("eleve_id"))
        champs = self._champs_eleve(self._champs(ch, CHAMPS_ELEVE))
        avant = ", ".join(
            f"{CHAMPS_ELEVE[c]} {_valeur(self._actuel(db, eleve, c))} → {_valeur(v)}" for c, v in champs.items()
        )
        eleve_id = eleve.id
        return Ligne(f"{_nom(eleve)} : {avant}", lambda db: self._ecrire_eleve(db, eleve_id, champs))

    def _inscription(self, db: Session, ecole_id: int, ch: dict) -> tuple[Compte, Cours, bool]:
        eleve = self._eleve(db, ecole_id, ch.get("eleve_id"))
        cours = self._un_cours(db, ecole_id, ch.get("cours_id"))
        inscrit = db.scalar(
            select(eleves_cours.c.eleve_id).where(eleves_cours.c.eleve_id == eleve.id, eleves_cours.c.cours_id == cours.id)
        ) is not None
        return eleve, cours, inscrit

    def _inscrire_cours(self, db: Session, ecole_id: int, ch: dict) -> Ligne:
        eleve, cours, inscrit = self._inscription(db, ecole_id, ch)
        if inscrit:
            raise Refus(f"{_nom(eleve)} est déjà inscrit(e) en {cours.nom}")
        cours_id, eleve_id = cours.id, eleve.id
        return Ligne(f"Inscrire {_nom(eleve)} en {cours.nom}", lambda db: self.cours.inscrire_eleve(db, cours_id, eleve_id))

    def _retirer_cours(self, db: Session, ecole_id: int, ch: dict) -> Ligne:
        eleve, cours, inscrit = self._inscription(db, ecole_id, ch)
        if not inscrit:
            raise Refus(f"{_nom(eleve)} n'est pas inscrit(e) en {cours.nom}")
        cours_id, eleve_id = cours.id, eleve.id
        return Ligne(f"Retirer {_nom(eleve)} du cours {cours.nom}", lambda db: self.cours.desinscrire_eleve(db, cours_id, eleve_id))

    def _champs_contact(self, ch: dict) -> dict:
        return {c: (None if v is None else str(v).strip()) for c, v in self._champs(ch, CHAMPS_CONTACT).items()}

    def _ajouter_contact(self, db: Session, ecole_id: int, ch: dict) -> Ligne:
        eleve = self._eleve(db, ecole_id, ch.get("eleve_id"))
        champs = self._champs_contact(ch)
        texte = " ".join(v for v in champs.values() if v)
        eleve_id = eleve.id
        return Ligne(f"{_nom(eleve)} : nouveau contact {texte}", lambda db: self.eleves.ajouter_contact(db, eleve_id, **champs))

    def _modifier_contact(self, db: Session, ecole_id: int, ch: dict) -> Ligne:
        contact = db.get(ContactEleve, ch.get("contact_id")) if isinstance(ch.get("contact_id"), int) else None
        if contact is None:
            raise Refus(f"contact n° {ch.get('contact_id')} introuvable")
        eleve = self._eleve(db, ecole_id, contact.eleve_id)
        champs = self._champs_contact(ch)
        avant = ", ".join(f"{CHAMPS_CONTACT[c]} {_valeur(getattr(contact, c))} → {_valeur(v)}" for c, v in champs.items())
        contact_id = contact.id
        return Ligne(
            f"{_nom(eleve)}, contact {contact.prenom or ''} {contact.nom or ''} : {avant}",
            lambda db: self.eleves.modifier_contact(db, contact_id, **champs),
        )

    def _noter_paiement(self, db: Session, ecole_id: int, ch: dict) -> Ligne:
        eleve = self._eleve(db, ecole_id, ch.get("eleve_id"))
        try:
            montant = float(ch.get("montant"))
        except (TypeError, ValueError) as erreur:
            raise Refus("montant illisible") from erreur
        if montant <= 0:
            raise Refus("montant à noter : plus que 0 €")
        profil = db.scalar(select(ProfilEleve).where(ProfilEleve.compte_id == eleve.id))
        paye = (profil.montant_paye or 0) if profil else 0
        total = profil.montant_total_annee if profil else None
        sur = f" sur {total:g} €" if total else ""
        eleve_id = eleve.id

        def faire(db: Session) -> None:
            actuel = db.scalar(select(ProfilEleve).where(ProfilEleve.compte_id == eleve_id))
            if actuel is None:
                raise ValueError("fiche de l'élève introuvable")
            nouveau = round((actuel.montant_paye or 0) + montant, 2)
            champs = {"montant_paye": nouveau}
            if actuel.montant_total_annee and nouveau >= actuel.montant_total_annee:
                champs["statut_paiement"] = "paye"
            self.eleves.update_profil(db, eleve_id, **champs)

        return Ligne(f"{_nom(eleve)} : paiement de {montant:g} € (payé {paye:g} → {paye + montant:g} €{sur})", faire)

    def _seance(self, db: Session, cours_id: int, date: dt.date) -> int:
        for s in self.presence.lister_seances(db, cours_id):
            if s.date == date:
                return s.id
        return self.presence.creer_seance(db, cours_id, date).id

    def _presence_eleve(self, db: Session, ecole_id: int, ch: dict) -> Ligne:
        cours = self._un_cours(db, ecole_id, ch.get("cours_id"))
        eleve = self._eleve(db, ecole_id, ch.get("eleve_id"))
        date = _date(ch.get("date"))
        statut = ch.get("statut")
        if statut not in STATUTS_PRESENCE:
            raise Refus("statut : present, absent ou retard")
        inscrit = db.scalar(
            select(eleves_cours.c.eleve_id).where(eleves_cours.c.eleve_id == eleve.id, eleves_cours.c.cours_id == cours.id)
        )
        if inscrit is None:
            raise Refus(f"{_nom(eleve)} n'est pas inscrit(e) en {cours.nom}")
        cours_id, eleve_id = cours.id, eleve.id
        return Ligne(
            f"{cours.nom}, {_jour(date)} : {_nom(eleve)} {STATUTS_PRESENCE[statut]}",
            lambda db: self.presence.set_presence_eleve(db, self._seance(db, cours_id, date), eleve_id, statut),
        )

    def _heures_professeur(self, db: Session, ecole_id: int, ch: dict) -> Ligne:
        cours = self._un_cours(db, ecole_id, ch.get("cours_id"))
        prof = self._prof(db, ecole_id, ch.get("professeur_id"))
        date = _date(ch.get("date"))
        permis = {"heure_debut_reelle": "début", "heure_fin_reelle": "fin", "depassement_minutes": "dépassement"}
        champs = self._champs(ch, permis)
        for cle in ("heure_debut_reelle", "heure_fin_reelle"):
            if cle in champs and not HEURE.match(str(champs[cle])):
                raise Refus(f"{permis[cle]} : HH:MM attendu")
        if "depassement_minutes" in champs:
            try:
                champs["depassement_minutes"] = int(champs["depassement_minutes"])
            except (TypeError, ValueError) as erreur:
                raise Refus("dépassement : un nombre de minutes") from erreur
        donne = db.scalar(
            select(cours_professeurs.c.cours_id).where(
                cours_professeurs.c.cours_id == cours.id, cours_professeurs.c.professeur_id == prof.id
            )
        )
        if donne is None:
            raise Refus(f"{_nom(prof)} ne donne pas le cours {cours.nom}")
        texte = ", ".join(f"{permis[c]} {v}" for c, v in champs.items())
        cours_id, prof_id = cours.id, prof.id
        return Ligne(
            f"{cours.nom}, {_jour(date)} : {_nom(prof)} {texte}",
            lambda db: self.presence.set_presence_prof(db, self._seance(db, cours_id, date), prof_id, **champs),
        )

    def _modifier_cours(self, db: Session, ecole_id: int, ch: dict) -> Ligne:
        cours = self._un_cours(db, ecole_id, ch.get("cours_id"))
        champs = {c: (None if v is None else str(v).strip()) for c, v in self._champs(ch, CHAMPS_COURS).items()}
        for cle in ("heure_debut", "heure_fin"):
            if champs.get(cle) and not HEURE.match(champs[cle]):
                raise Refus(f"{CHAMPS_COURS[cle]} : HH:MM attendu")
        if "nom" in champs and not champs["nom"]:
            raise Refus("nom du cours vide")
        avant = ", ".join(f"{CHAMPS_COURS[c]} {_valeur(getattr(cours, c))} → {_valeur(v)}" for c, v in champs.items())
        cours_id = cours.id
        return Ligne(f"Cours {cours.nom} : {avant}", lambda db: self.cours.update(db, cours_id, **champs))

    def _professeur_cours(self, db: Session, ecole_id: int, ch: dict) -> tuple[Cours, Compte, bool]:
        cours = self._un_cours(db, ecole_id, ch.get("cours_id"))
        prof = self._prof(db, ecole_id, ch.get("professeur_id"))
        donne = db.scalar(
            select(cours_professeurs.c.cours_id).where(
                cours_professeurs.c.cours_id == cours.id, cours_professeurs.c.professeur_id == prof.id
            )
        ) is not None
        return cours, prof, donne

    def _ajouter_professeur_cours(self, db: Session, ecole_id: int, ch: dict) -> Ligne:
        cours, prof, donne = self._professeur_cours(db, ecole_id, ch)
        if donne:
            raise Refus(f"{_nom(prof)} donne déjà {cours.nom}")
        cours_id, prof_id = cours.id, prof.id
        return Ligne(f"{_nom(prof)} donnera aussi le cours {cours.nom}", lambda db: self.cours.ajouter_professeur(db, cours_id, prof_id))

    def _retirer_professeur_cours(self, db: Session, ecole_id: int, ch: dict) -> Ligne:
        cours, prof, donne = self._professeur_cours(db, ecole_id, ch)
        if not donne:
            raise Refus(f"{_nom(prof)} ne donne pas {cours.nom}")
        cours_id, prof_id = cours.id, prof.id
        return Ligne(f"{_nom(prof)} ne donnera plus le cours {cours.nom}", lambda db: self.cours.retirer_professeur(db, cours_id, prof_id))

    def _eleves_choregraphie(self, db: Session, ecole_id: int, ids) -> list[Compte]:
        if not isinstance(ids, list):
            raise Refus("eleve_ids : une liste de numéros")
        return [self._eleve(db, ecole_id, i) for i in ids]

    def _creer_choregraphie(self, db: Session, ecole_id: int, ch: dict) -> Ligne:
        cours = self._un_cours(db, ecole_id, ch.get("cours_id"))
        champs = {c: (None if v is None else str(v).strip()) for c, v in self._champs(ch, CHAMPS_CHOREGRAPHIE).items()}
        nom = champs.pop("nom", None) or str(ch.get("nom") or "").strip()
        if not nom:
            raise Refus("nom de la chorégraphie obligatoire")
        eleves = self._eleves_choregraphie(db, ecole_id, ch.get("eleve_ids") or [])
        details = [f"{CHAMPS_CHOREGRAPHIE[c]} {_valeur(v)}" for c, v in champs.items()]
        if eleves:
            details.append(f"{len(eleves)} élèves : " + ", ".join(_nom(e) for e in eleves))
        cours_id, eleve_ids = cours.id, [e.id for e in eleves]
        return Ligne(
            f"Nouvelle chorégraphie « {nom} » ({cours.nom})" + (f" : {' ; '.join(details)}" if details else ""),
            lambda db: self.choregraphies.create(db, cours_id, nom, eleve_ids=eleve_ids, **champs),
        )

    def _modifier_choregraphie(self, db: Session, ecole_id: int, ch: dict) -> Ligne:
        chore, cours = self._choregraphie(db, ecole_id, ch.get("choregraphie_id"))
        champs = {
            c: (None if v is None else str(v).strip())
            for c, v in self._champs(ch, CHAMPS_CHOREGRAPHIE, obligatoire="eleve_ids" not in ch).items()
        }
        if "nom" in champs and not champs["nom"]:
            raise Refus("nom de la chorégraphie vide")
        details = [f"{CHAMPS_CHOREGRAPHIE[c]} {_valeur(getattr(chore, c))} → {_valeur(v)}" for c, v in champs.items()]
        eleve_ids = None
        if "eleve_ids" in ch:
            eleves = self._eleves_choregraphie(db, ecole_id, ch.get("eleve_ids"))
            eleve_ids = [e.id for e in eleves]
            avant = set(db.scalars(select(choregraphies_eleves.c.eleve_id).where(choregraphies_eleves.c.choregraphie_id == chore.id)))
            ajoutes = [_nom(e) for e in eleves if e.id not in avant]
            retires = [_nom(c) for c in (db.get(Compte, i) for i in avant - set(eleve_ids)) if c]
            if ajoutes:
                details.append("ajouter " + ", ".join(ajoutes))
            if retires:
                details.append("retirer " + ", ".join(retires))
        if not details:
            raise Refus("rien ne change")
        chore_id = chore.id
        return Ligne(
            f"Chorégraphie « {chore.nom} » ({cours.nom}) : " + " ; ".join(details),
            lambda db: self.choregraphies.update(db, chore_id, eleve_ids=eleve_ids, **champs),
        )
