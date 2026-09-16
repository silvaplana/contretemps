"""Régression : une vidéo réelle (prise sur un Samsung Android, signalée
par l'utilisateur — "Pokawa", "elle n'a pas de vignette") a des
métadonnées de couleur (VUI H.264) invalides qu'un ffmpeg récent refuse
de décoder ("Invalid color range"), pour la vignette (poster.py) ET la
compression (compression.py), alors que le fichier n'est pas corrompu.
Voir videos/normaliser_video.py pour le correctif (repli automatique).

`tests/fixtures/video_couleurs_invalides.mp4` : extrait d'1s de la vraie
vidéo signalée (juste l'image, sans le son — pas nécessaire pour ce test),
recadré par copie de flux (jamais ré-encodé, pour garder le problème
intact)."""

from pathlib import Path

from videos.compression import compresser
from videos.normaliser_video import corriger_metadonnees_couleur
from videos.poster import generer_poster

_FICHIER_PROBLEMATIQUE = (
    Path(__file__).resolve().parent / "fixtures" / "video_couleurs_invalides.mp4"
)


def test_corriger_metadonnees_couleur_produit_un_fichier_lisible(tmp_path):
    dest = tmp_path / "corrige.mp4"
    assert corriger_metadonnees_couleur(_FICHIER_PROBLEMATIQUE, dest) is True
    assert dest.exists()
    assert dest.stat().st_size > 0


def test_generer_poster_reussit_grace_au_repli(tmp_path):
    """Sans le repli (voir poster.py:generer_poster), ffmpeg échoue tout
    court sur ce fichier — vérifié manuellement avant le correctif."""
    dest = tmp_path / "poster.jpg"
    assert generer_poster(_FICHIER_PROBLEMATIQUE, dest) is True
    assert dest.exists()
    assert dest.stat().st_size > 0


def test_compresser_reussit_grace_au_repli(tmp_path):
    dest = tmp_path / "compresse.mp4"
    assert compresser(_FICHIER_PROBLEMATIQUE, dest) is True
    assert dest.exists()
    assert dest.stat().st_size > 0


def test_corriger_metadonnees_couleur_fichier_absent_echoue_proprement(tmp_path):
    assert corriger_metadonnees_couleur(tmp_path / "inexistant.mp4", tmp_path / "dest.mp4") is False
