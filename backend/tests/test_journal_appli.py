"""Journal de l'appli : les demandes échouées notées par le téléphone."""

from app import journal_appli


def test_lines_are_appended_then_read(client, tmp_path, monkeypatch, capsys):
    file = tmp_path / "journal-appli.log"
    monkeypatch.setenv("FICHIER_JOURNAL_APPLI", str(file))
    entry = {"at": "2026-11-20T23:10:00", "method": "GET", "path": "/eleves?ecole_id=1", "reason": "réseau\ncoupé"}

    r = client.post(journal_appli.PATH, json=[entry], headers={"X-Compte-Id": "7"})

    assert r.status_code == 204
    line = file.read_text(encoding="utf-8")
    assert "| fiche 7 | 2026-11-20T23:10:00 | GET /eleves?ecole_id=1 | réseau coupé\n" in line
    monkeypatch.setattr("sys.argv", ["journal_appli"])
    journal_appli.main()
    assert "GET /eleves?ecole_id=1" in capsys.readouterr().out


def test_file_stays_small(tmp_path, monkeypatch):
    file = tmp_path / "journal-appli.log"
    monkeypatch.setenv("FICHIER_JOURNAL_APPLI", str(file))
    monkeypatch.setattr(journal_appli, "MAX_BYTES", 2000)
    entry = journal_appli.Entry(at="t", method="GET", path="/eleves", reason="x" * 50)

    for _ in range(100):
        journal_appli.append("1", [entry])

    assert file.stat().st_size <= 2000
    assert file.read_text(encoding="utf-8").startswith("20")
