"""L'adresse de diagnostic de Fights (Seb, 13/11) : lecture seule, avec une
clé ; sans clé configurée, elle n'existe pas."""


def test_diagnostic_fights(client, monkeypatch):
    monkeypatch.delenv("FIGHTS_DIAG_KEY", raising=False)
    assert client.get("/diagnostic/fights", headers={"X-Diag-Key": "x" * 40}).status_code == 404
    monkeypatch.setenv("FIGHTS_DIAG_KEY", "k" * 40)
    assert client.get("/diagnostic/fights").status_code == 404
    assert client.get("/diagnostic/fights", headers={"X-Diag-Key": "x" * 40}).status_code == 404
    r = client.get("/diagnostic/fights", headers={"X-Diag-Key": "k" * 40})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain")
    r = client.get("/diagnostic/fights?seance=999", headers={"X-Diag-Key": "k" * 40})
    assert r.text.strip() == "Séance introuvable."
    monkeypatch.setenv("FIGHTS_DIAG_KEY", "court")
    assert client.get("/diagnostic/fights", headers={"X-Diag-Key": "court"}).status_code == 404


def test_ecart_des_poignets_bras_leves():
    """Lecture de séance : l'écart des poignets quand les deux ont les bras
    levés, pour régler les poings touchés (Seb, 13/11, séance 9)."""
    from app.lire_seance_fights import _raised
    from session_clips.signals import Frame
    from tests.test_session_clips_cutting import pose

    lignes = []
    _raised([Frame(t=1.0, people=[pose(100, "touch"), pose(140, "touch", wrist_dx=-40)]), Frame(t=2.0, people=[pose(100), pose(300)])], lignes.append)
    assert lignes[0].startswith("bras levés tous les deux : 1 images") and "1.0 s · écart des poignets 0.00" in lignes[1]
