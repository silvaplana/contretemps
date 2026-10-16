"""Table `ecoles` (voir spec/SPEC.md §6.1). Juste la forme des données —
la logique (création avec ses codes par défaut, etc.) vit dans ecoles.py.
"""

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, Text, UniqueConstraint, event, text
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Ecole(Base):
    """Un tenant. Le nom seul n'est pas unique : deux écoles peuvent
    partager le même nom (ex. deux associations "Contretemps" dans des
    villes différentes) — c'est le couple (nom, code_postal) qui l'est.
    """

    __tablename__ = "ecoles"
    __table_args__ = (UniqueConstraint("nom", "code_postal", name="uq_ecole_nom_code_postal"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nom: Mapped[str] = mapped_column(String(150), nullable=False)
    code_postal: Mapped[str] = mapped_column(String(10), nullable=False)
    # Coordonnées (spec §6.1, demande du 2026-10-15) : optionnelles, elles
    # remplacent sur la facture et le dossier d'inscription les valeurs de
    # inscriptions/coordonnees_association.py. Le SIRET est rangé sans
    # espaces (14 chiffres, voir ecoles.py:normaliser_siret).
    adresse: Mapped[str | None] = mapped_column(Text, nullable=True)
    ville: Mapped[str | None] = mapped_column(String(100), nullable=True)
    siret: Mapped[str | None] = mapped_column(String(14), nullable=True)
    # IBAN (demande du 2026-10-15) : rangé sans espaces, en majuscules,
    # clé de contrôle vérifiée (voir ecoles.py:normaliser_iban).
    iban: Mapped[str | None] = mapped_column(String(34), nullable=True)

    # --- Personnalisation de l'application (spec §2.7, §5.1.1, §6.1 ;
    # 2026-10-15). Vide = valeur par défaut de Contretemps (§7). Les images
    # sont des chemins relatifs au dossier de personnalisation (voir
    # personnalisation/stockage.py) ; l'original est gardé pour pouvoir
    # changer de détourage sans renvoyer l'image.
    logo: Mapped[str | None] = mapped_column(String(300), nullable=True)
    logo_original: Mapped[str | None] = mapped_column(String(300), nullable=True)
    logo_detourage: Mapped[str | None] = mapped_column(String(20), nullable=True)
    nom_mode: Mapped[str] = mapped_column(String(10), nullable=False, default="texte")
    nom_image: Mapped[str | None] = mapped_column(String(300), nullable=True)
    nom_image_original: Mapped[str | None] = mapped_column(String(300), nullable=True)
    nom_image_detourage: Mapped[str | None] = mapped_column(String(20), nullable=True)
    slogan: Mapped[str | None] = mapped_column(String(80), nullable=True)
    couleur_fond: Mapped[str | None] = mapped_column(String(7), nullable=True)
    couleur_texte: Mapped[str | None] = mapped_column(String(7), nullable=True)
    couleur_accent: Mapped[str | None] = mapped_column(String(7), nullable=True)
    police: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Police du nom de l'école écrit en texte (ex. Great Vibes, l'écriture
    # du site de l'école) ; vide = la même police que l'appli.
    police_nom: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Police des titres de l'appli ; vide = celle des textes (`police`).
    police_titres: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Pareil pour le slogan.
    police_slogan: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Adresse web : https://<sous_domaine>.contretemps.silvaplana.cloud
    # (voir personnalisation/adresse.py). L'ancienne redirige 6 mois.
    sous_domaine: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    nom_appli: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ancien_sous_domaine: Mapped[str | None] = mapped_column(String(40), nullable=True, unique=True)
    ancien_sous_domaine_jusqu_au: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Augmenté à chaque changement d'apparence : les adresses des icônes en
    # dépendent, pour que téléphones et navigateurs reprennent les nouvelles.
    personnalisation_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Plus de codes d'accès depuis le 2026-10-01 (spec §2.2) : chacun a son
    # mot de passe (table acces_emails).
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    # Assistant ouvert aux admins et profs (Seb, 16 octobre) : dépense
    # maximale par mois civil, en dollars, réglée par le Super User (qui
    # n'est jamais bloqué). Voir ressources.py et assistant/receiver.py.
    assistant_plafond_mensuel_usd: Mapped[float] = mapped_column(
        Float, nullable=False, default=10.0, server_default="10"
    )

    # Sauvegarde programmée (Admin > École > menu > "Programmer sauvegarde
    # École") — EN BASE, pas en localStorage : décision utilisateur
    # explicite, tous les admins sur tous les appareils doivent voir/
    # modifier le même réglage unique (voir sauvegarde_worker.py, qui lit
    # ces colonnes pour savoir quand déclencher une sauvegarde côté
    # serveur).
    sauvegarde_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 'jour' | 'semaine' | 'mois'.
    sauvegarde_periodicite: Mapped[str] = mapped_column(String(20), nullable=False, default="semaine")
    # 0=lundi .. 6=dimanche — utilisé seulement si periodicite='semaine'
    # (voir sauvegarde_worker.py : ignoré sinon, 'mois' se cale sur le 1er
    # du mois par simplicité, voir sa docstring).
    sauvegarde_jour_semaine: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sauvegarde_heure: Mapped[str | None] = mapped_column(String(5), nullable=True)  # "HH:MM"
    # Dernière exécution RÉUSSIE (voir sauvegarde_worker.py) — évite de
    # se redéclencher plusieurs fois dans le même créneau si le worker
    # est relancé (redéploiement...).
    sauvegarde_derniere_execution: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


@event.listens_for(Ecole, "before_insert")
def _adresse_par_defaut(mapper, connexion, ecole: Ecole) -> None:
    """Toute école a une adresse web (spec §2.7). Le chemin normal la
    choisit avant (voir ecoles.py:create) ; ceci couvre les autres
    créations (tests, outils) : le nom normalisé, numéroté s'il est pris."""
    if ecole.sous_domaine:
        return
    from personnalisation.adresse import RESERVES, normaliser

    base = normaliser(f"{ecole.nom} {ecole.code_postal}") or "ecole"
    prises = {ligne[0] for ligne in connexion.execute(text("SELECT sous_domaine FROM ecoles"))}
    adresse, numero = base, 2
    while adresse in prises or adresse in RESERVES or len(adresse) < 3:
        adresse, numero = f"{base}-{numero}", numero + 1
    ecole.sous_domaine = adresse
