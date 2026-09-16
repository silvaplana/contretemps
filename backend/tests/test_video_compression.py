"""Tests de la compression vidéo a posteriori (voir videos/compression.py
et app/video_compression_worker.py)."""

from pathlib import Path

from comptes import Comptes
from cours import CoursService
from ecoles import Ecoles
from videos import DOSSIER_VIDEOS_LIVE, Videos, chemin_relatif, dossier_ecole

_FICHIER_DEMO = (
    Path(__file__).resolve().parents[1] / "videos_reference" / "1" / "bang-bang-lent.mp4"
)


def _setup(db_session):
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    admin = Comptes().create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia")
    cours = CoursService().create(db_session, ecole_id=ecole.id, nom="Eveil")
    return ecole, cours, admin


def test_videos_a_compresser_ignore_en_cours_et_deja_compresse(db_session):
    ecole, cours, admin = _setup(db_session)
    videos_client = Videos(cours=CoursService())

    en_cours = videos_client.create(
        db_session, cours_id=cours.id, nom="En cours", lien_fichier="", uploaded_by=admin.id,
        statut="en_cours",
    )
    deja_compresse = videos_client.create(
        db_session, cours_id=cours.id, nom="Déjà fait", lien_fichier="x.mp4",
        uploaded_by=admin.id, statut="complete", compresse=True,
    )
    a_faire = videos_client.create(
        db_session, cours_id=cours.id, nom="À compresser", lien_fichier="y.mp4",
        uploaded_by=admin.id, statut="complete",
    )

    a_faire_ids = {v.id for v in videos_client.videos_a_compresser(db_session)}
    assert en_cours.id not in a_faire_ids
    assert deja_compresse.id not in a_faire_ids
    assert a_faire.id in a_faire_ids


def test_compresser_remplace_le_fichier_et_reduit_la_taille(db_session):
    """Fichier de démo réel (voir test_videos.py) — vérifie juste que le
    résultat existe, est bien du H.264/AAC lisible (durée retrouvée
    identique) et plus petit, pas la valeur exacte (dépend de la version
    ffmpeg)."""
    ecole, cours, admin = _setup(db_session)
    videos_client = Videos(cours=CoursService())

    dossier = dossier_ecole(ecole.id)
    chemin = dossier / "original.mp4"
    chemin.write_bytes(_FICHIER_DEMO.read_bytes())
    taille_originale = chemin.stat().st_size

    video = videos_client.create(
        db_session, cours_id=cours.id, nom="À compresser",
        lien_fichier=chemin_relatif(ecole.id, "original.mp4"),
        uploaded_by=admin.id, statut="complete",
    )

    try:
        assert videos_client.compresser(db_session, video) is True
        assert video.compresse is True
        assert video.lien_fichier.endswith(".mp4")
        chemin_final = DOSSIER_VIDEOS_LIVE / video.lien_fichier
        assert chemin_final.exists()
        assert chemin_final.stat().st_size < taille_originale
        assert not chemin.with_name("original-c.mp4").exists()  # fichier temporaire nettoyé
    finally:
        (DOSSIER_VIDEOS_LIVE / video.lien_fichier).unlink(missing_ok=True)
        chemin.unlink(missing_ok=True)


def test_compresser_fichier_source_manquant_echoue_proprement(db_session):
    ecole, cours, admin = _setup(db_session)
    videos_client = Videos(cours=CoursService())
    video = videos_client.create(
        db_session, cours_id=cours.id, nom="Fichier absent",
        lien_fichier=chemin_relatif(ecole.id, "inexistant.mp4"),
        uploaded_by=admin.id, statut="complete",
    )
    assert videos_client.compresser(db_session, video) is False
    assert video.compresse is False
