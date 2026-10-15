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


def test_menage_des_fichiers_orphelins(db_session, tmp_path, monkeypatch):
    """Restes d'anciens bugs (vu le 2026-10-15 : 220 Mo comptés en trop) :
    seuls les fichiers qui ne servent à rien et ont plus d'un jour partent."""
    import datetime as dt
    import os

    import videos.videos as module_videos
    from videos.models import Televersement

    monkeypatch.setattr(module_videos, "DOSSIER_VIDEOS_LIVE", tmp_path)
    ecole, cours, admin = _setup(db_session)
    dossier = tmp_path / str(ecole.id)
    (dossier / "_uploads").mkdir(parents=True)
    vieux = (dt.datetime.now() - dt.timedelta(days=2)).timestamp()

    def fichier(nom, age=vieux):
        chemin = dossier / nom
        chemin.write_bytes(b"x")
        os.utime(chemin, (age, age))
        return chemin

    utile = fichier("utile.mp4")
    apercu = fichier("utile.jpg")
    Videos().create(
        db_session, ecole_id=ecole.id, nom="Gardée", uploaded_by=admin.id,
        lien_fichier=f"{ecole.id}/utile.mp4", poster=f"{ecole.id}/utile.jpg",
    )
    orphelin = fichier("reste-de-bug.mp4")
    recent = fichier("tout-frais.mp4", age=dt.datetime.now().timestamp())
    original = fichier("original.mp4")
    fichier("original.mp4.a-effacer", age=dt.datetime.now().timestamp())
    envoi_inconnu = fichier("_uploads/perdu.part")
    db_session.add(Televersement(id="encours", ecole_id=ecole.id, extension=".mp4", octets_total=10))
    db_session.commit()
    envoi_en_cours = fichier("_uploads/encours.part", age=dt.datetime.now().timestamp())

    effaces = Videos().effacer_orphelins(db_session)

    assert set(effaces) == {orphelin.resolve(), envoi_inconnu.resolve()}
    for garde in (utile, apercu, recent, original, envoi_en_cours):
        assert garde.exists()


def test_supprimer_une_video_efface_ses_envois(db_session, monkeypatch):
    """La base réutilise le numéro d'une vidéo supprimée : ses envois (et
    un fichier partiel) partent avec elle."""
    from videos.stockage import chemin_televersement
    from videos.models import Televersement

    ecole, cours, admin = _setup(db_session)
    videos_client = Videos()
    video = videos_client.create(db_session, ecole_id=ecole.id, nom="V", lien_fichier="", uploaded_by=admin.id)
    db_session.add(Televersement(id="interrompu", ecole_id=ecole.id, extension=".mp4", octets_total=10, video_id=video.id))
    db_session.commit()
    partiel = chemin_televersement(ecole.id, "interrompu")
    partiel.write_bytes(b"x")
    assert videos_client.delete(db_session, video.id) is True
    assert not partiel.exists() and db_session.get(Televersement, "interrompu") is None
