"""Logique métier des écoles (voir spec/SPEC.md §2.3 et §6.1) — aucune
dépendance FastAPI ici, juste des méthodes appelées par receiver.py.
"""

from __future__ import annotations

import datetime as dt

from personnalisation.adresse import AdresseInvalide, normaliser, verifier
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .models import Ecole


def normaliser_iban(iban: str | None) -> str | None:
    """« fr76 3000 6000 0112 3456 7890 189 » -> « FR7630006000011234567890189 » ;
    vide -> None. Lève ValueError si la forme ou la clé de contrôle (norme
    ISO 13616, reste 1 modulo 97) ne va pas."""
    texte = "".join((iban or "").split()).upper()
    if not texte:
        return None
    if not (15 <= len(texte) <= 34 and texte[:2].isalpha() and texte[2:4].isdigit() and texte.isalnum()):
        raise ValueError("Cet IBAN n'a pas la bonne forme (ex. FR76 3000 6000 0112 3456 7890 189).")
    nombre = "".join(str(int(c, 36)) for c in texte[4:] + texte[:4])
    if int(nombre) % 97 != 1:
        raise ValueError("Cet IBAN est incorrect : vérifiez-le, un caractère est sans doute mal recopié.")
    return texte


def normaliser_siret(siret: str | None) -> str | None:
    """« 123 456 789 00012 » -> « 12345678900012 » ; vide -> None. Lève
    ValueError si ce ne sont pas 14 chiffres (spec §6.1)."""
    chiffres = "".join((siret or "").split())
    if not chiffres:
        return None
    if not (chiffres.isdigit() and len(chiffres) == 14):
        raise ValueError("Le SIRET doit compter 14 chiffres.")
    return chiffres


def normaliser_email(email: str | None) -> str | None:
    """« Tresorier@Asso.fr » -> « tresorier@asso.fr » ; vide -> None. Lève
    ValueError si ce n'est visiblement pas une adresse."""
    texte = (email or "").strip().lower()
    if not texte:
        return None
    nom, _, domaine = texte.partition("@")
    if not nom or "." not in domaine or " " in texte or domaine.startswith(".") or domaine.endswith("."):
        raise ValueError(f"« {email.strip()} » n'est pas une adresse mail valide.")
    return texte


class Ecoles:
    def list(self, db: Session) -> list[Ecole]:
        return list(db.scalars(select(Ecole)))

    def get(self, db: Session, ecole_id: int) -> Ecole | None:
        return db.get(Ecole, ecole_id)

    def find_by_nom_code_postal(self, db: Session, nom: str, code_postal: str) -> Ecole | None:
        """Le couple (nom, code_postal) identifie une école de façon unique
        (voir §6.1) — utilisé au login pour savoir dans quelle école un
        compte doit être recherché."""
        return db.scalar(
            select(Ecole).where(Ecole.nom == nom, Ecole.code_postal == code_postal)
        )

    # --- Adresse web (spec §2.7) ---

    def adresse_prise(self, db: Session, adresse: str, sauf_ecole_id: int | None = None) -> bool:
        """Prise par une autre école, comme adresse actuelle ou comme
        ancienne adresse qui redirige encore."""
        aujourdhui = dt.date.today()
        requete = select(Ecole.id).where(
            or_(
                Ecole.sous_domaine == adresse,
                (Ecole.ancien_sous_domaine == adresse) & (Ecole.ancien_sous_domaine_jusqu_au >= aujourdhui),
            )
        )
        if sauf_ecole_id is not None:
            requete = requete.where(Ecole.id != sauf_ecole_id)
        return db.scalar(requete) is not None

    def proposer_adresse(
        self, db: Session, nom: str, ville: str | None = None, code_postal: str | None = None,
        sauf_ecole_id: int | None = None,
    ) -> str:
        """Le nom normalisé ; s'il est réservé ou pris, la ville, puis
        nom-ville (ou nom-code postal) ; puis un numéro à la suite."""
        candidats = [normaliser(nom), normaliser(ville or ""), normaliser(f"{nom} {ville or code_postal or ''}")]
        for candidat in candidats:
            try:
                propre = verifier(candidat)
            except AdresseInvalide:
                continue
            if not self.adresse_prise(db, propre, sauf_ecole_id):
                return propre
        base = next((c for c in candidats if len(c) >= 2), "ecole")
        numero = 2
        while True:
            candidat = f"{base[:36]}-{numero}"
            if not self.adresse_prise(db, candidat, sauf_ecole_id):
                return candidat
            numero += 1

    def disponibilite(self, db: Session, adresse: str, ecole_id: int | None = None) -> dict:
        """Pour la vérification pendant la frappe : `raison` vaut
        'invalide', 'reserve' ou 'pris' ; `proposition` est une adresse libre."""
        # Proposition : la ville de l'école (ou son code postal) d'abord,
        # comme à la création (spec §2.7).
        ecole = self.get(db, ecole_id) if ecole_id is not None else None
        ville = ecole.ville if ecole is not None else None
        code_postal = ecole.code_postal if ecole is not None else None
        try:
            propre = verifier(adresse)
        except AdresseInvalide as erreur:
            base = normaliser(adresse) or "ecole"
            return {
                "adresse": normaliser(adresse),
                "disponible": False,
                "raison": erreur.raison,
                "proposition": self.proposer_adresse(db, base, ville, code_postal, ecole_id)
                if erreur.raison == "reserve"
                else None,
            }
        if self.adresse_prise(db, propre, ecole_id):
            return {
                "adresse": propre,
                "disponible": False,
                "raison": "pris",
                "proposition": self.proposer_adresse(db, propre, ville, code_postal, ecole_id),
            }
        return {"adresse": propre, "disponible": True, "raison": None, "proposition": None}

    def par_adresse(self, db: Session, adresse: str) -> tuple[Ecole | None, bool]:
        """(école, adresse ancienne ?) : l'école dont c'est l'adresse, ou
        l'ancienne adresse qui redirige encore."""
        ecole = db.scalar(select(Ecole).where(Ecole.sous_domaine == adresse))
        if ecole is not None:
            return ecole, False
        ecole = db.scalar(
            select(Ecole).where(
                Ecole.ancien_sous_domaine == adresse,
                Ecole.ancien_sous_domaine_jusqu_au >= dt.date.today(),
            )
        )
        return ecole, ecole is not None

    def changer_adresse(self, db: Session, ecole: Ecole, adresse: str) -> Ecole:
        """Lève AdresseInvalide ou ValueError (prise). L'ancienne adresse
        redirige vers la nouvelle pendant 6 mois (spec §2.7)."""
        propre = verifier(adresse)
        if propre == ecole.sous_domaine:
            return ecole
        if self.adresse_prise(db, propre, ecole.id):
            raise ValueError("Cette adresse est déjà prise par une autre école.")
        if ecole.ancien_sous_domaine == propre:
            ecole.ancien_sous_domaine = None
            ecole.ancien_sous_domaine_jusqu_au = None
        else:
            ecole.ancien_sous_domaine = ecole.sous_domaine
            ecole.ancien_sous_domaine_jusqu_au = dt.date.today() + dt.timedelta(days=183)
        ecole.sous_domaine = propre
        ecole.personnalisation_version = (ecole.personnalisation_version or 1) + 1
        db.commit()
        db.refresh(ecole)
        return ecole

    def create(
        self,
        db: Session,
        nom: str,
        code_postal: str,
        sous_domaine: str | None = None,
        ville: str | None = None,
    ) -> Ecole:
        """Toute école a une adresse web (spec §2.7) : celle demandée
        (vérifiée), sinon une proposée d'après le nom. Lève AdresseInvalide
        ou ValueError (prise)."""
        if sous_domaine:
            sous_domaine = verifier(sous_domaine)
            if self.adresse_prise(db, sous_domaine):
                raise ValueError("Cette adresse est déjà prise par une autre école.")
        else:
            sous_domaine = self.proposer_adresse(db, nom, ville, code_postal)
        ecole = Ecole(nom=nom, code_postal=code_postal, sous_domaine=sous_domaine, ville=ville)
        db.add(ecole)
        db.commit()
        db.refresh(ecole)
        return ecole

    def update(self, db: Session, ecole_id: int, **champs) -> Ecole | None:
        """Lève ValueError (message montrable) pour un SIRET invalide."""
        ecole = self.get(db, ecole_id)
        if ecole is None:
            return None
        if "siret" in champs:
            champs["siret"] = normaliser_siret(champs["siret"])
        if "iban" in champs:
            champs["iban"] = normaliser_iban(champs["iban"])
        for cle in ("email_contact", "email_tresorier"):
            if cle in champs:
                champs[cle] = normaliser_email(champs[cle])
        for cle in ("adresse", "ville"):
            if cle in champs:
                champs[cle] = (champs[cle] or "").strip() or None
        # `champs` ne contient déjà que les champs explicitement fournis
        # (exclude_unset=True côté receiver) — un `if valeur is not None`
        # ici empêchait à tort de vider un champ nullable.
        for cle, valeur in champs.items():
            setattr(ecole, cle, valeur)
        db.commit()
        db.refresh(ecole)
        return ecole
