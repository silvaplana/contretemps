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
