"""PDF des Docs ouvert dans la visionneuse du téléphone, par un lien signé
(documents_contretemps/lien_fichier.py)."""

import io

import pytest
from test_documents import Docs, _saison, ecole, stockage  # noqa: F401

pytestmark = pytest.mark.rbac_reel


def test_lien_signe_vers_le_pdf(client, ecole):  # noqa: F811
    prof, eleve = Docs(client, ecole["id"], ecole["prof"]), Docs(client, ecole["id"], ecole["eleve"])
    node_id = prof.fichier("PV.pdf", _saison(prof)["id"], contenu=b"%PDF-1.4 un").json()["id"]

    # Seul qui peut lire le fichier reçoit le lien.
    assert eleve.get(f"/nodes/{node_id}/link").status_code == 404
    url = prof.get(f"/nodes/{node_id}/link").json()["url"]

    # Le lien s'ouvre sans session, dans la page.
    reponse = client.get(url)
    assert reponse.status_code == 200 and reponse.content == b"%PDF-1.4 un"
    assert reponse.headers["content-disposition"].startswith("inline")
    assert client.get(url.replace("&s=", "&s=x")).status_code == 403

    # Une nouvelle version : l'ancien lien ne sert plus.
    prof.c.post(f"{prof.base}/nodes/{node_id}/versions", files={"file": ("PV.pdf", io.BytesIO(b"%PDF-1.4 deux"))}, headers=prof.h)
    assert client.get(url).status_code == 404
    assert client.get(prof.get(f"/nodes/{node_id}/link").json()["url"]).content == b"%PDF-1.4 deux"
