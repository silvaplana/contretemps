"""Personnalisation de l'application par école (spec §2.7, §5.1.1).

- Ce que voit l'appli (`vue`) : nom, nom sous l'icône, slogan, couleurs,
  police, logo, nom en image — les valeurs par défaut de Contretemps (§7)
  pour tout champ vide.
- Les images (logo, nom en image) : envoyées en brouillon, traitées
  (détourage au choix), regardées avant/après, puis validées ou non.
- Ce que lit le téléphone à l'installation : le manifest et les icônes,
  fabriqués pour l'école de l'adresse visitée (en-tête Host).
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
from collections.abc import Callable
from pathlib import Path

from ecoles.models import Ecole
from sqlalchemy.orm import Session

from . import images
from .adresse import GENERIQUE

DOSSIER_PERSONNALISATION = Path(os.environ.get("PERSONNALISATION_DIR", "./data/personnalisation"))
DOSSIER_DEFAUT = Path(__file__).resolve().parent / "defaut"

# Domaine des adresses d'école : https://<adresse>.<DOMAINE_ECOLES>.
DOMAINE_ECOLES = os.environ.get("DOMAINE_ECOLES", "contretemps.silvaplana.cloud")

DEFAUTS = {
    "slogan": "Gestion d'école de danse du cours au gala",
    "couleur_fond": "#FDECD8",
    "couleur_texte": "#3A2410",
    "couleur_accent": "#D8722A",
}
# Polices hébergées (frontend/public/fonts, licence SIL OFL) ; vide = système.
POLICES = {"montserrat", "poppins", "prompt", "nunito", "josefin-sans", "playfair-display"}
# Pour le nom de l'école seulement : en plus, une écriture manuscrite,
# illisible pour des textes courants (demande du 2026-10-15).
POLICES_NOM = POLICES | {"great-vibes"}
DETOURAGES = ("aucun", "simple", "ia")
TYPES_IMAGE = ("logo", "nom")

_COULEUR = re.compile(r"^#[0-9A-Fa-f]{6}$")
_BROUILLON = re.compile(r"^brouillon-[0-9a-f]{16}(-original)?\.png$")
# Images validées, gardées pour pouvoir y revenir (demande du 2026-10-15).
_IMAGE_GARDEE = re.compile(r"^(logo|nom)-(\d+)(-original)?\.png$")


class PersonnalisationRefusee(ValueError):
    """Le message est montrable."""


def adresse_de_l_ecole(ecole: Ecole) -> str:
    return f"https://{ecole.sous_domaine}.{DOMAINE_ECOLES}"


def etiquette_du_host(host: str | None) -> str | None:
    """« le-beausset.contretemps.silvaplana.cloud:443 » -> « le-beausset ».
    Accepte aussi « <adresse>.localhost » pour le développement. None pour
    toute autre adresse (dont l'adresse générique)."""
    hote = (host or "").split(":")[0].strip().lower().rstrip(".")
    for domaine in (DOMAINE_ECOLES, "localhost"):
        suffixe = f".{domaine}"
        if hote.endswith(suffixe):
            etiquette = hote[: -len(suffixe)]
            if etiquette and "." not in etiquette:
                return etiquette
    return None


class Personnalisation:
    def __init__(
        self,
        ecoles,
        detourage_ia: Callable[[images.Image.Image], images.Image.Image] | None = None,
        noter_cout: Callable[[Session, int, str, float, str], None] | None = None,
    ) -> None:
        """`detourage_ia` : détourage par IA (rembg), absent si non installé.
        `noter_cout(db, ecole_id, poste, cout_usd, detail)` : relève chaque
        opération d'IA (« Usage ressources et IA », voir ressources/)."""
        self.ecoles = ecoles
        self.detourage_ia = detourage_ia
        self.noter_cout = noter_cout

    # --- Lecture ---

    def detourages_disponibles(self) -> list[str]:
        return [d for d in DETOURAGES if d != "ia" or self.detourage_ia is not None]

    def vue(self, ecole: Ecole | None) -> dict:
        """Ce que l'appli applique ; `ecole=None` : l'adresse générique."""
        if ecole is None:
            return {
                "ecole_id": None, "sous_domaine": GENERIQUE, "nom": "Contretemps", "nom_appli": "Contretemps",
                "nom_mode": "texte", "slogan": DEFAUTS["slogan"], "couleur_fond": DEFAUTS["couleur_fond"],
                "couleur_texte": DEFAUTS["couleur_texte"], "couleur_accent": DEFAUTS["couleur_accent"],
                "police": None, "police_nom": None, "police_slogan": None, "logo_personnalise": False, "nom_image": False, "version": 0,
                "adresse": f"https://{GENERIQUE}.{DOMAINE_ECOLES}",
            }
        return {
            "ecole_id": ecole.id,
            "sous_domaine": ecole.sous_domaine,
            "nom": ecole.nom,
            "nom_appli": ecole.nom_appli or ecole.nom,
            "nom_mode": ecole.nom_mode if ecole.nom_image else "texte",
            "slogan": ecole.slogan or DEFAUTS["slogan"],
            "couleur_fond": ecole.couleur_fond or DEFAUTS["couleur_fond"],
            "couleur_texte": ecole.couleur_texte or DEFAUTS["couleur_texte"],
            "couleur_accent": ecole.couleur_accent or DEFAUTS["couleur_accent"],
            "police": ecole.police,
            "police_nom": ecole.police_nom,
            "police_slogan": ecole.police_slogan,
            "logo_personnalise": bool(ecole.logo),
            "nom_image": bool(ecole.nom_image),
            "version": ecole.personnalisation_version or 1,
            "adresse": adresse_de_l_ecole(ecole),
        }

    def ecole_du_host(self, db: Session, host: str | None) -> tuple[Ecole | None, bool]:
        """(école, adresse ancienne ?) de l'adresse visitée."""
        etiquette = etiquette_du_host(host)
        if etiquette is None or etiquette == GENERIQUE:
            return None, False
        return self.ecoles.par_adresse(db, etiquette)

    def existe(self, db: Session, domaine: str | None) -> bool:
        """Caddy demande s'il peut créer un certificat pour `domaine` (spec
        §2.7) : oui pour l'adresse générique et les adresses d'école."""
        etiquette = etiquette_du_host(domaine)
        if etiquette is None:
            return False
        if etiquette == GENERIQUE:
            return True
        ecole, _ = self.ecoles.par_adresse(db, etiquette)
        return ecole is not None

    # --- Modification ---

    def modifier(self, db: Session, ecole: Ecole, champs: dict) -> Ecole:
        for cle in ("couleur_fond", "couleur_texte", "couleur_accent"):
            if cle in champs:
                valeur = (champs[cle] or "").strip()
                if valeur and not _COULEUR.match(valeur):
                    raise PersonnalisationRefusee("Une couleur s'écrit #RRGGBB (ex. #D8722A).")
                champs[cle] = valeur.upper() or None
        for cle, permises in (("police", POLICES), ("police_nom", POLICES_NOM), ("police_slogan", POLICES_NOM)):
            if cle in champs:
                police = (champs[cle] or "").strip() or None
                if police is not None and police not in permises:
                    raise PersonnalisationRefusee("Cette police n'est pas proposée.")
                champs[cle] = police
        if "nom_mode" in champs and champs["nom_mode"] not in ("texte", "image"):
            raise PersonnalisationRefusee("Le nom s'affiche en texte ou en image.")
        for cle, longueur in (("slogan", 80), ("nom_appli", 30)):
            if cle in champs:
                valeur = (champs[cle] or "").strip()
                if len(valeur) > longueur:
                    raise PersonnalisationRefusee(f"{longueur} caractères au plus.")
                champs[cle] = valeur or None
        for cle, valeur in champs.items():
            setattr(ecole, cle, valeur)
        ecole.personnalisation_version = (ecole.personnalisation_version or 1) + 1
        db.commit()
        db.refresh(ecole)
        return ecole

    def revenir_au_defaut(self, db: Session, ecole: Ecole) -> Ecole:
        """Logo, nom en texte, slogan, couleurs et police par défaut ; ne
        touche ni à l'adresse ni au nom sous l'icône (spec §5.1.1)."""
        for cle in (
            "logo", "logo_original", "logo_detourage", "nom_image", "nom_image_original",
            "nom_image_detourage", "slogan", "couleur_fond", "couleur_texte", "couleur_accent", "police",
            "police_nom", "police_slogan",
        ):
            setattr(ecole, cle, None)
        ecole.nom_mode = "texte"
        ecole.personnalisation_version = (ecole.personnalisation_version or 1) + 1
        db.commit()
        # Les images validées restent dans l'historique (on peut y revenir) ;
        # seuls les brouillons et les icônes fabriquées disparaissent.
        for type_image in TYPES_IMAGE:
            self.annuler_image(ecole.id, type_image)
        shutil.rmtree(self._dossier(ecole.id) / "icones", ignore_errors=True)
        db.refresh(ecole)
        return ecole

    # --- Images : brouillon, détourage, validation ---

    def _dossier(self, ecole_id: int) -> Path:
        return DOSSIER_PERSONNALISATION / str(ecole_id)

    def _brouillon(self, ecole_id: int, type_image: str) -> Path:
        return self._dossier(ecole_id) / f"brouillon-{type_image}.json"

    def envoyer_image(
        self, db: Session, ecole: Ecole, type_image: str, contenu: bytes, type_mime: str,
        detourage: str | None = None,
    ) -> dict:
        """Nouvelle image en brouillon : l'original (en PNG) est gardé, puis
        traité avec le détourage demandé (par défaut : aucun si l'image a
        déjà de la transparence, simple sinon)."""
        image = images.ouvrir(contenu, type_mime)
        # Taille de travail : le détourage parcourt chaque pixel.
        image = images.reduire(image, 1400)
        if detourage is None:
            detourage = "aucun" if images.a_de_la_transparence(image) else "simple"
        dossier = self._dossier(ecole.id)
        dossier.mkdir(parents=True, exist_ok=True)
        original = f"brouillon-{secrets.token_hex(8)}-original.png"
        (dossier / original).write_bytes(images.en_png(image))
        brouillon = {"original": original, "couleur_fond_proposee": images.couleur_de_fond_proposee(image)}
        self._ecrire_brouillon(ecole.id, type_image, brouillon)
        return self.choisir_detourage(db, ecole, type_image, detourage)

    def choisir_detourage(self, db: Session, ecole: Ecole, type_image: str, detourage: str) -> dict:
        """Refait le traitement depuis l'original du brouillon (ou, à défaut,
        de l'image en place) : changer de détourage sans renvoyer l'image."""
        if detourage not in self.detourages_disponibles():
            raise PersonnalisationRefusee("Ce détourage n'est pas disponible.")
        brouillon = self._lire_brouillon(ecole.id, type_image)
        if brouillon is None:
            en_place = ecole.logo_original if type_image == "logo" else ecole.nom_image_original
            if not en_place:
                raise PersonnalisationRefusee("Envoyez d'abord une image.")
            brouillon = {"original": en_place, "couleur_fond_proposee": None}
        dossier = self._dossier(ecole.id)
        image = images.Image.open(dossier / brouillon["original"]).convert("RGBA")
        cout = 0.0
        if detourage == "simple":
            image = images.detourage_simple(image)
        elif detourage == "ia":
            image = self.detourage_ia(image)
            if self.noter_cout is not None:
                # Sur notre serveur, sans service payant : relevé à 0 $.
                self.noter_cout(db, ecole.id, "detourage_logo", cout, f"{type_image}, IA sur le serveur")
        image = images.recadrer(image)
        if type_image == "logo":
            image = images.reduire(image, images.COTE_MAX_LOGO)
        else:
            image.thumbnail((images.LARGEUR_MAX_NOM, images.LARGEUR_MAX_NOM // 2), images.Image.LANCZOS)
        ancien = brouillon.get("traite")
        traite = f"brouillon-{secrets.token_hex(8)}.png"
        (dossier / traite).write_bytes(images.en_png(image))
        if ancien and ancien != brouillon["original"]:
            (dossier / ancien).unlink(missing_ok=True)
        brouillon.update(traite=traite, detourage=detourage, cout_usd=cout)
        self._ecrire_brouillon(ecole.id, type_image, brouillon)
        return {
            "type": type_image,
            "original": brouillon["original"],
            "traite": traite,
            "detourage": detourage,
            "detourages_disponibles": self.detourages_disponibles(),
            "couleur_fond_proposee": brouillon.get("couleur_fond_proposee"),
            "cout_usd": cout,
        }

    def valider_image(self, db: Session, ecole: Ecole, type_image: str) -> Ecole:
        """Le brouillon devient l'image de l'école (version suivante)."""
        brouillon = self._lire_brouillon(ecole.id, type_image)
        if brouillon is None or "traite" not in brouillon:
            raise PersonnalisationRefusee("Aucune image en attente.")
        dossier = self._dossier(ecole.id)
        version = (ecole.personnalisation_version or 1) + 1
        nom_traite = f"{type_image}-{version}.png"
        nom_original = f"{type_image}-{version}-original.png"
        (dossier / brouillon["traite"]).rename(dossier / nom_traite)
        if brouillon["original"].startswith("brouillon-"):
            (dossier / brouillon["original"]).rename(dossier / nom_original)
        else:
            shutil.copyfile(dossier / brouillon["original"], dossier / nom_original)
        if type_image == "logo":
            ecole.logo, ecole.logo_original, ecole.logo_detourage = nom_traite, nom_original, brouillon["detourage"]
        else:
            ecole.nom_image, ecole.nom_image_original = nom_traite, nom_original
            ecole.nom_image_detourage, ecole.nom_mode = brouillon["detourage"], "image"
        ecole.personnalisation_version = version
        db.commit()
        # Les précédentes restent dans l'historique (voir historique).
        self.annuler_image(ecole.id, type_image)
        db.refresh(ecole)
        return ecole

    # --- Historique des images validées (demande du 2026-10-15) ---

    def historique(self, ecole: Ecole, type_image: str) -> list[dict]:
        """Les images déjà validées pour ce type, la plus récente d'abord ;
        `actuelle` : celle en place."""
        dossier = self._dossier(ecole.id)
        en_place = ecole.logo if type_image == "logo" else ecole.nom_image
        resultat = []
        for chemin in dossier.glob(f"{type_image}-*.png") if dossier.exists() else []:
            correspondance = _IMAGE_GARDEE.match(chemin.name)
            if correspondance and not correspondance.group(3):
                resultat.append({"fichier": chemin.name, "version": int(correspondance.group(2)), "actuelle": chemin.name == en_place})
        return sorted(resultat, key=lambda image: image["version"], reverse=True)

    def reprendre_image(self, db: Session, ecole: Ecole, type_image: str, fichier: str) -> Ecole:
        """Remet en place une image de l'historique."""
        if fichier not in {image["fichier"] for image in self.historique(ecole, type_image)}:
            raise PersonnalisationRefusee("Cette image n'existe plus.")
        original = fichier.replace(".png", "-original.png")
        if not (self._dossier(ecole.id) / original).exists():
            original = fichier
        if type_image == "logo":
            ecole.logo, ecole.logo_original, ecole.logo_detourage = fichier, original, None
        else:
            ecole.nom_image, ecole.nom_image_original, ecole.nom_image_detourage = fichier, original, None
            ecole.nom_mode = "image"
        ecole.personnalisation_version = (ecole.personnalisation_version or 1) + 1
        db.commit()
        db.refresh(ecole)
        return ecole

    def supprimer_image(self, ecole: Ecole, type_image: str, fichier: str) -> None:
        """Retire une image de l'historique ; jamais celle en place."""
        images = {image["fichier"]: image for image in self.historique(ecole, type_image)}
        if fichier not in images:
            raise PersonnalisationRefusee("Cette image n'existe plus.")
        if images[fichier]["actuelle"]:
            raise PersonnalisationRefusee("C'est l'image en place : choisissez-en une autre d'abord.")
        dossier = self._dossier(ecole.id)
        (dossier / fichier).unlink(missing_ok=True)
        (dossier / fichier.replace(".png", "-original.png")).unlink(missing_ok=True)

    def annuler_image(self, ecole_id: int, type_image: str) -> None:
        brouillon = self._lire_brouillon(ecole_id, type_image)
        dossier = self._dossier(ecole_id)
        if brouillon:
            for cle in ("original", "traite"):
                nom = brouillon.get(cle)
                if nom and nom.startswith("brouillon-"):
                    (dossier / nom).unlink(missing_ok=True)
        self._brouillon(ecole_id, type_image).unlink(missing_ok=True)

    def _lire_brouillon(self, ecole_id: int, type_image: str) -> dict | None:
        chemin = self._brouillon(ecole_id, type_image)
        return json.loads(chemin.read_text()) if chemin.exists() else None

    def _ecrire_brouillon(self, ecole_id: int, type_image: str, brouillon: dict) -> None:
        self._brouillon(ecole_id, type_image).write_text(json.dumps(brouillon))

    def fichier_image(self, ecole: Ecole, nom: str) -> Path | None:
        """Fichier servi publiquement : le logo, le nom en image, ou un
        brouillon (nom tiré au hasard)."""
        if nom == "logo.png":
            return self._dossier(ecole.id) / ecole.logo if ecole.logo else DOSSIER_DEFAUT / "logo-contretemps.png"
        if nom == "nom.png":
            return self._dossier(ecole.id) / ecole.nom_image if ecole.nom_image else None
        if _BROUILLON.match(nom) or _IMAGE_GARDEE.match(nom):
            chemin = self._dossier(ecole.id) / nom
            return chemin if chemin.exists() else None
        return None

    # --- Ce que lit le téléphone à l'installation (spec §2.7) ---

    def manifest(self, ecole: Ecole | None) -> dict:
        vue = self.vue(ecole)
        v = f"?v={vue['version']}"
        icones = [
            {"src": f"/icons/icon-{taille}{suffixe}.png{v}", "sizes": f"{taille}x{taille}", "type": "image/png", "purpose": but}
            for taille in (192, 512)
            for suffixe, but in (("", "any"), ("-maskable", "maskable"))
        ]
        fond = self._couleur_appli(ecole)
        return {
            "name": vue["nom_appli"],
            "short_name": vue["nom_appli"],
            "description": vue["slogan"],
            "id": "/",
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "background_color": fond,
            "theme_color": fond,
            "icons": icones,
        }

    def _couleur_appli(self, ecole: Ecole | None) -> str:
        """Couleur de la barre et de l'écran de lancement de l'appli
        installée : celle de l'école si elle a personnalisé son logo ou son
        fond, sinon l'orange des icônes d'aujourd'hui."""
        if ecole is not None and (ecole.logo or ecole.couleur_fond):
            return self.vue(ecole)["couleur_fond"]
        return "#F46E19"

    def icone(self, ecole: Ecole | None, nom: str) -> bytes | None:
        """`nom` : icon-192.png, icon-512-maskable.png, favicon.png,
        apple-touch-icon.png. Sans logo ni couleur de fond personnalisés,
        les icônes d'aujourd'hui ; sinon fabriquées et gardées sur disque."""
        tailles = {
            "icon-192.png": (192, False), "icon-512.png": (512, False),
            "icon-192-maskable.png": (192, True), "icon-512-maskable.png": (512, True),
            "favicon.png": (64, False), "apple-touch-icon.png": (180, False),
        }
        if nom not in tailles:
            return None
        if ecole is None or not (ecole.logo or ecole.couleur_fond):
            return (DOSSIER_DEFAUT / nom).read_bytes()
        taille, maskable = tailles[nom]
        version = ecole.personnalisation_version or 1
        cache = self._dossier(ecole.id) / "icones" / f"v{version}-{nom}"
        if not cache.exists():
            cache.parent.mkdir(parents=True, exist_ok=True)
            for ancien in cache.parent.glob(f"v*-{nom}"):
                ancien.unlink(missing_ok=True)
            logo = images.Image.open(self.fichier_image(ecole, "logo.png")).convert("RGBA")
            cache.write_bytes(images.icone(logo, self.vue(ecole)["couleur_fond"], taille, maskable))
        return cache.read_bytes()

    def entete_html(self, ecole: Ecole | None) -> str:
        """Les balises que l'iPhone lit à l'installation, avant que
        l'appli ne démarre (injectées dans index.html, voir frontend/Caddyfile)."""
        from html import escape

        vue = self.vue(ecole)
        nom = escape(vue["nom_appli"])
        return (
            f"<title>{nom}</title>\n"
            f'    <meta name="apple-mobile-web-app-title" content="{nom}" />\n'
            f'    <meta name="theme-color" content="{escape(self._couleur_appli(ecole))}" />'
        )
