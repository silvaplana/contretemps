"""Logique des vidéos (voir spec/SPEC.md §6.8) : recevoir un fichier par
blocs, le stocker, le mesurer, le compresser, le supprimer, compter la
place occupée.

Module générique (voir models.py) : il ne connaît ni les cours ni les
chorégraphies. Le métier qui rattache des vidéos à ses objets s'inscrit à
`quand_supprimee` pour défaire ses liens quand une vidéo disparaît.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from collections.abc import Callable

from saisons.portee import toutes_saisons

from .compression import compresser as compresser_fichier
from .duree import duree_secondes
from .models import Televersement, Video
from .poster import generer_poster
from .schemas import UsageVideosEcole, VideoUsage
from .stockage import DOSSIER_VIDEOS_LIVE, chemin_relatif, chemin_televersement, dossier_ecole

# Une session abandonnée (fichier choisi puis onglet fermé sans "Ajouter"
# ni "Annuler" — voir spec/discussion : "si on ferme l'app, on annule
# tout") ne doit pas laisser un fichier partiel indéfiniment sur le
# disque. Nettoyée paresseusement à chaque nouvelle session créée (voir
# _nettoyer_abandonnes) plutôt que via un worker dédié — pas besoin de
# plus pour un cas aussi rare.
DELAI_ABANDON = dt.timedelta(hours=6)


class DecalageInvalide(Exception):
    """Le bloc envoyé ne commence pas là où le serveur l'attend (voir
    Videos.ecrire_bloc) — le navigateur a pu perdre le fil après une
    coupure réseau. `octets_recus` : le VRAI décalage actuel côté
    serveur, pour que le client resynchronise son envoi dessus plutôt que
    de deviner."""

    def __init__(self, octets_recus: int) -> None:
        self.octets_recus = octets_recus
        super().__init__(f"Décalage invalide, reprendre à {octets_recus}")


class Videos:
    def __init__(self) -> None:
        self._a_la_suppression: list[Callable[[Session, int], None]] = []

    def quand_supprimee(self, rappel: Callable[[Session, int], None]) -> None:
        """`rappel(db, video_id)` est appelé juste avant la suppression
        d'une vidéo, d'où qu'elle vienne (route, annulation d'un envoi) :
        le métier y défait ses propres liens."""
        self._a_la_suppression.append(rappel)

    def par_ids(self, db: Session, video_ids: list[int]) -> dict[int, Video]:
        if not video_ids:
            return {}
        return {v.id: v for v in db.scalars(select(Video).where(Video.id.in_(video_ids)))}

    def get(self, db: Session, video_id: int) -> Video | None:
        return db.get(Video, video_id)

    def create(
        self,
        db: Session,
        ecole_id: int,
        nom: str,
        lien_fichier: str,
        uploaded_by: int,
        **champs,
    ) -> Video:
        video = Video(
            ecole_id=ecole_id, nom=nom, lien_fichier=lien_fichier, uploaded_by=uploaded_by,
            **champs,
        )
        db.add(video)
        db.commit()
        db.refresh(video)
        return video

    # --- Upload par blocs (voir Televersement dans models.py) ---
    #
    # 3 temps :
    #  1. creer_televersement : dès le fichier choisi/filmé, AVANT toute
    #     métadonnée — juste une session, pas encore de ligne `Video`.
    #  2. ecrire_bloc : appelé en boucle pendant que l'admin remplit le
    #     formulaire (titre/description) en parallèle.
    #  3. finaliser : au clic "Ajouter" — crée la ligne tout de suite,
    #     même si l'envoi n'est pas fini (statut 'en_cours'), voir
    #     _finaliser_fichier pour la suite une fois le fichier complet.

    def creer_televersement(
        self, db: Session, ecole_id: int, extension: str, octets_total: int
    ) -> Televersement:
        self._nettoyer_abandonnes(db)
        televersement = Televersement(
            id=uuid4().hex,
            ecole_id=ecole_id,
            extension=extension or ".mp4",
            octets_total=octets_total,
        )
        db.add(televersement)
        db.commit()
        db.refresh(televersement)
        return televersement

    def ecrire_bloc(
        self, db: Session, upload_id: str, decalage: int, donnees: bytes
    ) -> Televersement | None:
        """`decalage` : position déclarée par le client pour ce bloc — DOIT
        correspondre à `octets_recus` (voir DecalageInvalide) : détecte un
        bloc rejoué/manquant après une coupure réseau plutôt que d'écrire
        au mauvais endroit et corrompre le fichier."""
        televersement = self.obtenir_televersement(db, upload_id)
        if televersement is None:
            return None
        if decalage != televersement.octets_recus:
            raise DecalageInvalide(televersement.octets_recus)

        chemin = chemin_televersement(televersement.ecole_id, upload_id)
        with open(chemin, "ab") as sortie:
            sortie.write(donnees)
        televersement.octets_recus += len(donnees)
        if televersement.octets_recus >= televersement.octets_total:
            televersement.complet = True
        db.commit()
        db.refresh(televersement)

        # "Ajouter" a déjà été cliqué (voir finaliser) : ce dernier bloc
        # termine le travail tout de suite, sans attendre un appel
        # supplémentaire du frontend.
        if televersement.complet and televersement.video_id is not None:
            video = self.get(db, televersement.video_id)
            if video is not None:
                self._finaliser_fichier(db, video, televersement)
        return televersement

    def obtenir_televersement(self, db: Session, upload_id: str) -> Televersement | None:
        return db.get(Televersement, upload_id)

    def annuler_televersement(self, db: Session, upload_id: str) -> bool:
        televersement = self.obtenir_televersement(db, upload_id)
        if televersement is None:
            return False
        # Même si "Ajouter" a déjà été cliqué (video_id renseigné), voir
        # spec : "l'appui sur annuler arrête tout" — supprime aussi la
        # ligne Video créée entre-temps, pas seulement la session.
        if televersement.video_id is not None:
            self.delete(db, televersement.video_id)
        chemin_televersement(televersement.ecole_id, upload_id).unlink(missing_ok=True)
        db.delete(televersement)
        db.commit()
        return True

    def finaliser(
        self,
        db: Session,
        upload_id: str,
        nom: str,
        uploaded_by: int,
        description: str = "",
    ) -> Video | None:
        """Clic "Ajouter" — crée la ligne tout de suite (voir Video.statut :
        'en_cours' si le fichier n'est pas encore complet à cet instant,
        auquel cas ecrire_bloc terminera le travail au dernier bloc)."""
        televersement = self.obtenir_televersement(db, upload_id)
        if televersement is None:
            return None
        if televersement.video_id is not None:
            # Double clic/double appel (voir AdminEleves.jsx pour un motif
            # similaire) : déjà finalisé, renvoie la ligne existante plutôt
            # que d'en créer une 2e.
            return self.get(db, televersement.video_id)

        video = self.create(
            db,
            ecole_id=televersement.ecole_id,
            nom=nom,
            lien_fichier="",
            uploaded_by=uploaded_by,
            description=description,
            statut="complete" if televersement.complet else "en_cours",
        )
        televersement.video_id = video.id
        db.commit()

        if televersement.complet:
            self._finaliser_fichier(db, video, televersement)
            db.refresh(video)
        return video

    def _finaliser_fichier(self, db: Session, video: Video, televersement: Televersement) -> None:
        """Fichier complet (voir ecrire_bloc/finaliser, les 2 points
        d'entrée possibles selon l'ordre d'arrivée entre le dernier bloc et
        le clic "Ajouter") — déplace le fichier partiel vers son
        emplacement définitif, mesure durée + vignette (même ffmpeg que
        l'ancien upload direct), passe la vidéo en 'complete'. La
        compression, elle, est une tâche de fond séparée (voir
        app/video_compression_worker.py), jamais ici (ne doit pas retarder
        la disponibilité de la vidéo).

        La ligne `televersement` N'EST PAS supprimée ici (contrairement à
        annuler_televersement) : `finaliser` s'en sert pour rester
        idempotent sur un double appel (voir son docstring) — reste
        simplement une petite ligne inerte, jamais reprise par
        _nettoyer_abandonnes puisque `video_id` est renseigné."""
        dossier = dossier_ecole(televersement.ecole_id)
        nom_disque = f"{uuid4().hex}{televersement.extension}"
        chemin_disque = dossier / nom_disque
        chemin_televersement(televersement.ecole_id, televersement.id).rename(chemin_disque)

        poster = None
        chemin_poster_disque = dossier / f"{Path(nom_disque).stem}.jpg"
        if generer_poster(chemin_disque, chemin_poster_disque):
            poster = chemin_relatif(televersement.ecole_id, chemin_poster_disque.name)

        video.lien_fichier = chemin_relatif(televersement.ecole_id, nom_disque)
        video.poster = poster
        video.duree_secondes = duree_secondes(chemin_disque)
        video.statut = "complete"
        db.commit()

    def _nettoyer_abandonnes(self, db: Session) -> None:
        """Fichier choisi puis onglet fermé sans "Ajouter" ni "Annuler" —
        voir DELAI_ABANDON. Appelé à chaque nouvelle session plutôt que par
        un worker dédié : ce cas doit rester rare, pas besoin de plus."""
        limite = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) - DELAI_ABANDON
        abandonnes = db.scalars(
            select(Televersement).where(
                Televersement.video_id.is_(None), Televersement.cree_le < limite
            )
        )
        for televersement in abandonnes:
            chemin_televersement(televersement.ecole_id, televersement.id).unlink(missing_ok=True)
            db.delete(televersement)
        db.commit()

    def update(self, db: Session, video_id: int, **champs) -> Video | None:
        video = self.get(db, video_id)
        if video is None:
            return None
        # `champs` ne contient déjà que les champs explicitement fournis
        # (le receiver appelle model_dump(exclude_unset=True)) — un
        # `if valeur is not None` ici empêchait à tort de vider un champ
        # nullable (ex. effacer une description).
        for cle, valeur in champs.items():
            setattr(video, cle, valeur)
        db.commit()
        db.refresh(video)
        return video

    def delete(self, db: Session, video_id: int) -> bool:
        video = self.get(db, video_id)
        if video is None:
            return False
        # Le métier défait d'abord ses liens vers cette vidéo (voir
        # quand_supprimee). L'autre risque d'orphelin, c'est
        # le FICHIER lui-même : sans ça, le fichier (et sa vignette)
        # restait sur le disque pour toujours, jamais compté nulle part
        # une fois la ligne supprimée (bug latent trouvé en construisant
        # le panneau "Usage vidéo", qui aurait fini par lister du vide).
        for rappel in self._a_la_suppression:
            rappel(db, video_id)
        for chemin_relatif in (video.lien_fichier, video.poster):
            if not chemin_relatif:
                continue
            # `chemin_relatif` est en théorie toujours une valeur qu'on a
            # nous-même écrite (voir stockage.chemin_relatif), mais rien
            # n'empêche l'API de l'accepter arbitraire (VideoModification
            # accepte n'importe quelle chaîne) — un chemin ABSOLU dans
            # `/` ferait sortir `DOSSIER_VIDEOS_LIVE / chemin_relatif` du
            # dossier vidéos (Path : joindre avec un chemin absolu
            # REMPLACE la base). Vérifié avant de supprimer quoi que ce
            # soit, plutôt que de faire confiance à la valeur en base.
            cible = (DOSSIER_VIDEOS_LIVE / chemin_relatif).resolve()
            if cible.is_relative_to(DOSSIER_VIDEOS_LIVE.resolve()):
                cible.unlink(missing_ok=True)
        db.delete(video)
        db.commit()
        return True

    # --- Compression a posteriori (voir app/video_compression_worker.py) ---

    def videos_a_compresser(self, db: Session) -> list[Video]:
        return list(
            db.scalars(
                select(Video).where(
                    Video.statut == "complete",
                    Video.compresse.is_(False),
                    Video.lien_fichier != "",
                )
            )
        )

    def compresser(self, db: Session, video: Video) -> bool:
        """`False` si la compression échoue (voir compression.py) —
        `video.compresse` reste False, retenté au prochain passage du
        worker. En cas de succès, remplace le fichier d'origine (jamais
        gardé en plus, voir décision utilisateur : économiser l'espace
        disque) — toujours sous extension .mp4 (H.264/AAC, voir
        compression.py), même si le fichier d'origine était dans un autre
        conteneur (ex. .mov)."""
        chemin_source = DOSSIER_VIDEOS_LIVE / video.lien_fichier
        chemin_dest = chemin_source.with_name(f"{chemin_source.stem}-c.mp4")
        if not compresser_fichier(chemin_source, chemin_dest):
            chemin_dest.unlink(missing_ok=True)
            return False
        chemin_final = chemin_source.with_suffix(".mp4")
        chemin_source.unlink(missing_ok=True)
        chemin_dest.rename(chemin_final)
        video.lien_fichier = str(Path(video.lien_fichier).with_suffix(".mp4"))
        video.compresse = True
        db.commit()
        return True

    def usage_ecole(self, db: Session, ecole_id: int) -> UsageVideosEcole:
        """Panneau "Usage vidéo" (Admin > École) : Go utilisés, minutes de
        vidéo, top 10 par taille décroissante — toutes les vidéos AVEC un
        vrai fichier (lien_fichier non vide) de l'école. La taille se lit
        sur le disque à la demande (pas stockée, toujours exacte même si
        un fichier est remplacé à la main) ; la durée vient de
        Video.duree_secondes (mesurée une fois, voir duree.py).

        Saisons (spec §2.6) : tout porte sur la saison affichée, sauf
        `total_toutes_saisons_*`, cumul de toutes les saisons de l'école."""
        with toutes_saisons(db):
            toutes = self._tailles(self._videos_avec_fichier(db, ecole_id))
        mesurees = self._tailles(self._videos_avec_fichier(db, ecole_id))
        lignes = [
            VideoUsage(
                id=video.id, titre=video.nom, taille_octets=taille, duree_secondes=video.duree_secondes
            )
            for video, taille in mesurees
        ]
        lignes.sort(key=lambda ligne: ligne.taille_octets, reverse=True)
        return UsageVideosEcole(
            total_octets=sum(taille for _, taille in mesurees),
            total_secondes=sum(video.duree_secondes or 0 for video, _ in mesurees),
            total_toutes_saisons_octets=sum(taille for _, taille in toutes),
            total_toutes_saisons_secondes=sum(video.duree_secondes or 0 for video, _ in toutes),
            top_videos=lignes[:10],
        )

    def _videos_avec_fichier(self, db: Session, ecole_id: int) -> list[Video]:
        # La saison affichée filtre d'elle-même (voir saisons/portee.py).
        return list(
            db.scalars(select(Video).where(Video.ecole_id == ecole_id, Video.lien_fichier != ""))
        )

    def _tailles(self, videos: list[Video]) -> list[tuple[Video, int]]:
        """(vidéo, taille sur le disque) ; un fichier manquant est ignoré,
        pas d'erreur 500."""
        resultat = []
        for video in videos:
            try:
                resultat.append((video, (DOSSIER_VIDEOS_LIVE / video.lien_fichier).stat().st_size))
            except OSError:
                continue
        return resultat
