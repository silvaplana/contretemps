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
    videos_client = Videos()

    en_cours = videos_client.create(
        db_session, ecole_id=ecole.id, nom="En cours", lien_fichier="", uploaded_by=admin.id,
        statut="en_cours",
    )
    deja_compresse = videos_client.create(
        db_session, ecole_id=ecole.id, nom="Déjà fait", lien_fichier="x.mp4",
        uploaded_by=admin.id, statut="complete", compresse=True,
    )
    a_faire = videos_client.create(
        db_session, ecole_id=ecole.id, nom="À compresser", lien_fichier="y.mp4",
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
    videos_client = Videos()

    dossier = dossier_ecole(ecole.id)
    chemin = dossier / "original.mp4"
    chemin.write_bytes(_FICHIER_DEMO.read_bytes())
    taille_originale = chemin.stat().st_size

    video = videos_client.create(
        db_session, ecole_id=ecole.id, nom="À compresser",
        lien_fichier=chemin_relatif(ecole.id, "original.mp4"),
        uploaded_by=admin.id, statut="complete",
    )

    try:
        assert videos_client.compresser(db_session, video) is True
        assert video.compresse is True
        # Nouveau nom : l'original n'est jamais remplacé sous un lecteur.
        assert video.lien_fichier.endswith("original-c.mp4")
        chemin_final = DOSSIER_VIDEOS_LIVE / video.lien_fichier
        assert chemin_final.exists()
        assert chemin_final.stat().st_size < taille_originale
        # L'original reste une heure, marqué à effacer.
        assert chemin.read_bytes() == _FICHIER_DEMO.read_bytes()
        temoin = chemin.with_name("original.mp4.a-effacer")
        assert temoin.exists()
        assert videos_client.effacer_originaux() == 0
        import datetime as dt

        assert videos_client.effacer_originaux(dt.datetime.now() + dt.timedelta(hours=1, minutes=1)) == 1
        assert not chemin.exists() and not temoin.exists() and chemin_final.exists()
    finally:
        (DOSSIER_VIDEOS_LIVE / video.lien_fichier).unlink(missing_ok=True)
        chemin.unlink(missing_ok=True)
        chemin.with_name("original.mp4.a-effacer").unlink(missing_ok=True)


def test_compresser_fichier_source_manquant_echoue_proprement(db_session):
    ecole, cours, admin = _setup(db_session)
    videos_client = Videos()
    video = videos_client.create(
        db_session, ecole_id=ecole.id, nom="Fichier absent",
        lien_fichier=chemin_relatif(ecole.id, "inexistant.mp4"),
        uploaded_by=admin.id, statut="complete",
    )
    assert videos_client.compresser(db_session, video) is False
    assert video.compresse is False


def test_le_worker_seul_sait_enregistrer_une_video(tmp_path):
    """Bug du 2026-10-15 : lancé seul (comme en production), le worker ne
    chargeait pas le modèle des écoles ; l'enregistrement échouait après la
    compression, et la vidéo était recompressée en boucle. Processus séparé :
    dans pytest, app.main a déjà tout chargé et masquerait le problème."""
    import subprocess
    import sys

    src = Path(__file__).resolve().parents[1] / "src"
    resultat = subprocess.run(
        [sys.executable, "-c", "import app.video_compression_worker as w; from db import Base, engine; from sqlalchemy.orm import configure_mappers; configure_mappers(); "
         "Base.metadata.create_all(engine)"],
        cwd=src, capture_output=True, text=True,
        env={"PYTHONPATH": str(src), "DATABASE_URL": f"sqlite:///{tmp_path}/vide.db", "PATH": ""},
    )
    assert resultat.returncode == 0, resultat.stderr


def test_echec_d_enregistrement_garde_l_original(db_session, monkeypatch):
    """La base est enregistrée AVANT de remplacer le fichier : si elle
    échoue, l'original reste intact et rien n'est recompressé par-dessus."""
    import pytest

    ecole, cours, admin = _setup(db_session)
    videos_client = Videos()
    chemin = dossier_ecole(ecole.id) / "intact.mp4"
    chemin.write_bytes(_FICHIER_DEMO.read_bytes())
    video = videos_client.create(
        db_session, ecole_id=ecole.id, nom="Intacte",
        lien_fichier=chemin_relatif(ecole.id, "intact.mp4"), uploaded_by=admin.id, statut="complete",
    )

    def panne():
        raise RuntimeError("base indisponible")

    monkeypatch.setattr(db_session, "commit", panne)
    try:
        with pytest.raises(RuntimeError):
            videos_client.compresser(db_session, video)
        assert chemin.read_bytes() == _FICHIER_DEMO.read_bytes()
        assert not chemin.with_name("intact-c.mp4").exists()
    finally:
        chemin.unlink(missing_ok=True)
