"""Table des vidéos (voir spec/SPEC.md §6.8)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cours_id: Mapped[int] = mapped_column(ForeignKey("cours.id"), nullable=False, index=True)
    choregraphie_id: Mapped[int | None] = mapped_column(
        ForeignKey("choregraphies.id"), nullable=True, index=True
    )
    nom: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Chemin/URL, pas le fichier lui-même (voir §6.8).
    lien_fichier: Mapped[str] = mapped_column(String(500), nullable=False)
    # Vignette (chemin relatif, même convention que lien_fichier, voir
    # videos/stockage.py) — absente de la spec §6.8 d'origine : ajoutée
    # parce que les navigateurs mobiles (Chrome/Brave/Samsung Internet
    # Android testés) n'affichent PAS la 1re image d'une vidéo tant
    # qu'elle n'est pas jouée (juste une case noire + icône "média"),
    # contrairement à Chrome desktop — sans vignette, l'écran Vidéo
    # paraît cassé sur mobile alors que la lecture elle-même fonctionne.
    poster: Mapped[str | None] = mapped_column(String(500), nullable=True)
    date_publication: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("comptes.id"), nullable=False)
    # Durée réelle du fichier (secondes), lue une fois via ffmpeg (voir
    # videos/duree.py) — nullable : absente pour une vidéo sans fichier
    # (lien_fichier vide) ou pas encore mesurée. Sert au panneau "Usage
    # vidéo" (Admin > École) — la taille, elle, se lit directement sur le
    # disque à la demande (voir videos.py : usage_ecole), pas stockée.
    duree_secondes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Ordre manuel, utilisé uniquement dans le contexte d'une chorégraphie
    # (voir §6.8 : ignoré sur l'écran Vidéo, trié par date_publication là-bas).
    ordre: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Upload par blocs (voir Televersement ci-dessous et videos.py) : la
    # ligne peut exister en base AVANT que le fichier soit entièrement
    # reçu (demande utilisateur explicite : "Ajouter" enregistre tout de
    # suite, l'envoi continue en tâche de fond) — 'en_cours' tant que le
    # fichier n'est pas complet (poster/duree_secondes pas encore connus),
    # 'complete' une fois le fichier reçu en entier. 'complete' par défaut
    # pour les vidéos créées sans upload (démo, import) — jamais "en cours".
    statut: Mapped[str] = mapped_column(String(20), nullable=False, default="complete")
    # Compression a posteriori (voir app/video_compression_worker.py) :
    # tâche de fond séparée, jamais avant l'envoi (voir §8 spec — la
    # compression AVANT envoi ralentirait l'upload lui-même côté web, pas
    # d'encodeur matériel disponible dans un navigateur).
    compresse: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Televersement(Base):
    """Session d'upload par blocs (voir videos.py) — existe SEULEMENT
    pendant l'envoi, avant que l'admin ait cliqué "Ajouter" (pas encore de
    ligne `Video` à ce moment-là) et jusqu'à ce que le fichier soit reçu en
    entier. `video_id` se remplit au clic "Ajouter" (voir Videos.finaliser)
    même si l'envoi n'est pas terminé — le dernier bloc reçu déclenche
    alors la finalisation (poster/durée/statut) sans attendre un nouvel
    appel. Nettoyée : à la fin normale (fusionnée dans le fichier final,
    voir Videos._finaliser_fichier), sur "Annuler" (voir Videos.annuler),
    ou automatiquement si abandonnée (voir Videos._nettoyer_abandonnes)."""

    __tablename__ = "televersements_video"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    ecole_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id"), nullable=False)
    cours_id: Mapped[int] = mapped_column(ForeignKey("cours.id"), nullable=False)
    extension: Mapped[str] = mapped_column(String(20), nullable=False)
    octets_total: Mapped[int] = mapped_column(Integer, nullable=False)
    octets_recus: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    complet: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Rempli au clic "Ajouter" (voir Videos.finaliser) — tant qu'il est
    # vide, aucune ligne Video n'existe encore pour cet envoi.
    video_id: Mapped[int | None] = mapped_column(ForeignKey("videos.id"), nullable=True)
    cree_le: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
