"""Videos sent in a message (spec/modules/messagerie-instantanee.md §4.5):
in blocks, with a poster, read through a signed link, compressed by the
server when the phone could not."""

import subprocess

import imageio_ffmpeg
import pytest
from conftest import entetes_session

from app.main import app, messagerie_receiver
from comptes import Comptes, rbac
from cours import CoursService
from ecoles import Ecoles


@pytest.fixture(autouse=True)
def _stockage_temporaire(tmp_path, monkeypatch):
    monkeypatch.setattr(messagerie_receiver.attachments.storage, "root", tmp_path)
    return tmp_path


@pytest.fixture(scope="module")
def video(tmp_path_factory):
    """A real two-second clip (ffmpeg test pattern)."""
    chemin = tmp_path_factory.mktemp("clip") / "clip.mp4"
    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-f", "lavfi", "-i", "testsrc=duration=2:size=640x360:rate=25",
         "-pix_fmt", "yuv420p", str(chemin)],
        capture_output=True, check=True,
    )
    return chemin.read_bytes()


def _setup(client, db_session):
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    prof = Comptes().create(db_session, ecole_id=ecole.id, role="professeur", nom="Blanc", prenom="Ima")
    eleve = Comptes().create(db_session, ecole_id=ecole.id, role="eleve", nom="Perrin", prenom="Léon")
    cours = CoursService().create(db_session, ecole_id=ecole.id, nom="Eveil")
    CoursService().inscrire_eleve(db_session, cours.id, eleve.id)
    CoursService().ajouter_professeur(db_session, cours.id, prof.id)
    conv = client.post(
        "/conversations",
        params={"ecole_id": ecole.id},
        json={"membres": [{"membre_type": "cours", "membre_id": cours.id}]},
    ).json()
    app.dependency_overrides[rbac.compte_appelant] = lambda: prof
    return ecole, prof, eleve, conv


def _envoyer(client, conv_id, contenu, compressed=True, bloc=50_000):
    upload = client.post(
        f"/conversations/{conv_id}/video-uploads",
        json={"filename": "gala.mp4", "size": len(contenu), "compressed": compressed},
    ).json()
    reponse = None
    for debut in range(0, len(contenu), bloc):
        reponse = client.put(
            f"/video-uploads/{upload['id']}", params={"offset": debut}, content=contenu[debut : debut + bloc]
        )
        assert reponse.status_code == 200
    return reponse.json()


def test_video_in_blocks_becomes_an_attachment_with_poster_and_length(client, db_session, video):
    ecole, prof, _, conv = _setup(client, db_session)
    fin = _envoyer(client, conv["id"], video)
    piece = fin["attachment"]
    assert fin["received"] == len(video)
    assert piece["kind"] == "video"
    assert piece["duration"] == 2
    assert (piece["width"], piece["height"]) == (464, 261)  # the poster's proportions

    message = client.post(
        f"/conversations/{conv['id']}/messages",
        json={"expediteur_id": prof.id, "contenu": "", "attachment_ids": [piece["id"]]},
    ).json()
    assert message["attachments"][0]["kind"] == "video"
    assert client.get(f"/attachments/{piece['id']}/thumbnail").status_code == 200

    url = client.get(f"/attachments/{piece['id']}/link").json()["url"]
    app.dependency_overrides.pop(rbac.compte_appelant)  # the <video> tag has no session
    lecture = client.get(url, headers={"Range": "bytes=0-99"})
    assert lecture.status_code == 206
    assert lecture.content == video[:100]
    assert client.get(url.replace("s=", "s=x")).status_code == 403


def test_block_at_the_wrong_offset_says_where_to_resume(client, db_session, video):
    _, _, _, conv = _setup(client, db_session)
    upload = client.post(
        f"/conversations/{conv['id']}/video-uploads", json={"filename": "a.mp4", "size": len(video)}
    ).json()
    client.put(f"/video-uploads/{upload['id']}", params={"offset": 0}, content=video[:1000])
    rejoue = client.put(f"/video-uploads/{upload['id']}", params={"offset": 0}, content=video[:1000])
    assert rejoue.status_code == 409
    assert rejoue.json()["detail"] == {"received": 1000}


def test_video_over_100_mb_is_refused(client, db_session):
    _, _, _, conv = _setup(client, db_session)
    reponse = client.post(
        f"/conversations/{conv['id']}/video-uploads", json={"filename": "a.mp4", "size": 100 * 1024 * 1024 + 1}
    )
    assert reponse.status_code == 413


def test_server_compresses_a_video_the_phone_could_not(client, db_session, video, _stockage_temporaire):
    ecole, prof, _, conv = _setup(client, db_session)
    piece = _envoyer(client, conv["id"], video, compressed=False)["attachment"]
    attachments = messagerie_receiver.attachments
    avant = attachments.get(db_session, piece["id"]).sha256

    assert attachments.compress_pending(db_session) == 1
    apres = attachments.get(db_session, piece["id"])
    db_session.refresh(apres)
    assert apres.compressed and apres.sha256 != avant
    assert not attachments.storage.path(ecole.id, avant).exists()
    assert attachments.storage.thumbnail_path(ecole.id, apres.sha256).exists()
    assert attachments.compress_pending(db_session) == 0  # once only


@pytest.mark.rbac_reel
def test_only_members_send_a_video(client, db_session):
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    admin = Comptes().create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia")
    prof = Comptes().create(db_session, ecole_id=ecole.id, role="professeur", nom="Blanc", prenom="Ima")
    autre = Comptes().create(db_session, ecole_id=ecole.id, role="eleve", nom="Perrin", prenom="Léon")
    conv = client.post(
        "/dm",
        params={"ecole_id": ecole.id, "compte_a_id": admin.id, "compte_b_id": prof.id},
        headers=entetes_session(admin),
    ).json()
    refus = client.post(
        f"/conversations/{conv['id']}/video-uploads",
        json={"filename": "a.mp4", "size": 10},
        headers=entetes_session(autre),
    )
    assert refus.status_code == 403
