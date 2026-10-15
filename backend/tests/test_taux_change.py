"""Taux dollar -> euro (BCE) : une lecture par jour, dernier taux en secours."""

import io

import pytest
from change import TauxChange
from change import taux as module

XML = b"""<Cube><Cube time='2026-10-15'><Cube currency='USD' rate='1.1208'/>
<Cube currency='JPY' rate='170.1'/></Cube></Cube>"""


@pytest.fixture()
def bce(monkeypatch):
    monkeypatch.delenv("TAUX_EUR_PAR_USD", raising=False)
    appels = []

    def ouvrir(url, timeout):
        appels.append(url)
        if appels and getattr(ouvrir, "panne", False):
            raise OSError("hors ligne")
        return io.BytesIO(XML)

    monkeypatch.setattr(module.urllib.request, "urlopen", ouvrir)
    return ouvrir, appels


def test_lu_une_fois_par_jour_et_garde_sur_disque(bce, tmp_path, monkeypatch):
    ouvrir, appels = bce
    fichier = tmp_path / "taux.json"
    taux = TauxChange(fichier)
    premier = taux.taux()
    assert premier["eur_par_usd"] == pytest.approx(1 / 1.1208) and premier["date"] == "2026-10-15"
    taux.taux()
    assert len(appels) == 1  # pas une lecture à chaque demande
    # Redémarrage du serveur : le taux revient du disque, sans lecture.
    assert TauxChange(fichier).taux()["eur_par_usd"] == pytest.approx(1 / 1.1208) and len(appels) == 1
    # Un jour plus tard, la BCE ne répond pas : le dernier taux sert.
    ouvrir.panne = True
    monkeypatch.setattr(module.time, "time", lambda: 10**12)
    assert taux.taux()["eur_par_usd"] == pytest.approx(1 / 1.1208)


def test_secours_et_taux_fixe(bce, tmp_path, monkeypatch):
    ouvrir, _ = bce
    ouvrir.panne = True
    assert TauxChange(tmp_path / "rien.json").taux()["source"] == "secours"
    monkeypatch.setenv("TAUX_EUR_PAR_USD", "0.5")
    assert TauxChange().taux() == {"eur_par_usd": 0.5, "date": None, "source": "fixé"}
