"""Assistant de l'onglet Docs (prototype) : un faux Claude, aucun appel
réel. Vérifie la boucle d'outils, les cartes « Faire / Annuler » (rien
n'est fait par l'assistant lui-même) et l'accès réservé au Super User."""

import io
import json
from types import SimpleNamespace

import pytest
from app import main
from comptes import Comptes, rbac
from conftest import MOT_DE_PASSE, entetes_session
from ecoles import Ecoles
from securite import mots_de_passe

pytestmark = pytest.mark.rbac_reel


class Bloc(SimpleNamespace):
    def model_dump(self, exclude_none=False):
        return {k: v for k, v in vars(self).items() if not (exclude_none and v is None)}


def _message(*blocs, stop="end_turn"):
    usage = SimpleNamespace(input_tokens=1000, output_tokens=100, cache_read_input_tokens=0, cache_creation_input_tokens=0)
    return SimpleNamespace(content=list(blocs), stop_reason=stop, model="claude-opus-5-5", usage=usage)


class FauxFlux:
    def __init__(self, message):
        self.message = message

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        for b in self.message.content:
            if b.type == "text":
                yield SimpleNamespace(type="text", text=b.text)

    def get_final_message(self):
        return self.message


class FauxClaude:
    """Rejoue des réponses prévues et garde les demandes reçues."""

    def __init__(self, reponses):
        self.reponses = list(reponses)
        self.demandes = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **demande):
        self.demandes.append(json.loads(json.dumps(demande["messages"], default=str)))
        return FauxFlux(self.reponses.pop(0))


@pytest.fixture()
def monde(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(main.documents_client.storage, "root", tmp_path)
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    admin = Comptes().create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia")
    su = Comptes().enregistrer_superuser(
        db_session, nom="Richard", prenom="Sébastien", email="su@test.fr",
        mot_de_passe_hache=mots_de_passe.hacher(MOT_DE_PASSE),
    )
    return {"ecole": ecole, "admin": admin, "su": su}


def _en_superuser(client):
    jeton = client.post("/auth/login", json={"identifiant": "Sébastien Richard", "mot_de_passe": MOT_DE_PASSE}).json()["jeton"]
    return jeton


def _evenements(reponse):
    return [json.loads(ligne[6:]) for ligne in reponse.text.splitlines() if ligne.startswith("data: ")]


def test_l_assistant_lit_le_dossier_et_propose_sans_rien_faire(client, monde, monkeypatch):
    ecole = monde["ecole"]
    entetes = {"Authorization": f"Bearer {_en_superuser(client)}", rbac.ENTETE_COMPTE: str(monde["su"].id)}
    base = f"/documents/orgs/{ecole.id}"
    saison = next(e for e in client.get(f"{base}/spaces/private", headers=entetes).json()["items"] if e["system_kind"] == "period")
    client.post(
        f"{base}/files", data={"space": "private", "parent_id": str(saison["id"])},
        files={"file": ("Budget.txt", io.BytesIO(b"Loyer : 300 euros"))}, headers=entetes,
    )
    faux = FauxClaude([
        _message(Bloc(type="tool_use", id="t1", name="lister_dossier", input={"espace": "private", "dossier_id": saison["id"]}), stop="tool_use"),
        _message(Bloc(type="tool_use", id="t2", name="proposer_creer_dossier",
                      input={"espace": "private", "dossier_parent_id": saison["id"], "nom": "AG 2027"}), stop="tool_use"),
        _message(Bloc(type="text", text="Je vous propose de créer le dossier AG 2027.")),
    ])
    monkeypatch.setattr(main.assistant_client, "_client", faux)

    reponse = client.post(
        f"/assistant/orgs/{ecole.id}/messages",
        json={"texte": "Range un peu ce dossier", "contexte": {"space": "private", "folder_id": saison["id"]}},
        headers=entetes,
    )
    assert reponse.status_code == 200
    evenements = _evenements(reponse)
    types = [e["type"] for e in evenements]
    assert types[0] == "conversation" and types[-1] == "fin" and "erreur" not in types
    carte = next(e for e in evenements if e["type"] == "action")
    assert carte["kind"] == "creer_dossier" and carte["nom"] == "AG 2027"
    assert carte["libelle"].startswith("Créer le dossier « AG 2027 » dans Privé › Saison")
    assert "".join(e["texte"] for e in evenements if e["type"] == "texte") == "Je vous propose de créer le dossier AG 2027."

    # Le contexte (le dossier ouvert) accompagne la question.
    premiere = faux.demandes[0][0]["content"][0]["text"]
    assert "Contexte : la personne regarde le dossier « Privé › Saison" in premiere and "Range un peu ce dossier" in premiere
    # L'outil de lecture a renvoyé le contenu du dossier à Claude.
    resultat = faux.demandes[1][-1]["content"][0]
    assert resultat["tool_use_id"] == "t1" and "Budget.txt" in resultat["content"]
    # La proposition n'a rien créé.
    noms = [e["name"] for e in client.get(f"{base}/spaces/private?folder={saison['id']}", headers=entetes).json()["items"]]
    assert "AG 2027" not in noms

    # Même conversation au tour suivant : l'historique est rejoué tel quel, complété.
    conv_id = evenements[0]["id"]
    faux.reponses.append(_message(Bloc(type="text", text="Parfait.")))
    suite = client.post(
        f"/assistant/orgs/{ecole.id}/messages",
        json={"conversation_id": conv_id, "texte": "Merci", "contexte": {"actions": ["Fait : Créer le dossier « AG 2027 »"]}},
        headers=entetes,
    )
    assert _evenements(suite)[0]["id"] == conv_id
    assert len(faux.demandes[-1]) == 7
    assert "Suite à ta proposition : Fait" in faux.demandes[-1][-1]["content"][0]["text"]
    fin = _evenements(suite)[-1]
    assert fin["tour"]["modele"] == "Opus 5.5" and fin["tour"]["appels"] == 1 and fin["cout_total_usd"] > fin["cout_usd"]


def test_choix_du_modele(client, monde, monkeypatch):
    entetes = {"Authorization": f"Bearer {_en_superuser(client)}", rbac.ENTETE_COMPTE: str(monde["su"].id)}
    vus = []
    faux = FauxClaude([_message(Bloc(type="text", text="Bonjour."))] * 2)
    original = faux._stream
    faux.beta.messages.stream = lambda **d: (vus.append((d["model"], "fallbacks" in d)), original(**d))[1]
    monkeypatch.setattr(main.assistant_client, "_client", faux)
    url = f"/assistant/orgs/{monde['ecole'].id}/messages"
    fin = _evenements(client.post(url, json={"texte": "Bonjour", "modele": "claude-haiku-5-5"}, headers=entetes))[-1]
    assert fin["tour"]["modele"] == "Haiku 5.5"
    # Modèle inconnu : celui par défaut.
    client.post(url, json={"texte": "Bonjour", "modele": "gpt"}, headers=entetes)
    assert vus == [("claude-haiku-5-5", False), ("claude-opus-5-5", True)]
    # Chaque question est reportée dans « Usage des ressources & IA ».
    usage = client.get(f"/ecoles/{monde['ecole'].id}/ressources", headers=entetes).json()
    ligne = next(l for l in usage["ia"] if l["categorie"] == "chat_documents")
    assert ligne["libelle"] == "Chat documents" and ligne["nombre"] == 2 and ligne["cout_usd"] > 0
    # Cumul de la saison, rendu à chaque réponse et à l'ouverture de l'assistant.
    assert fin["cout_saison_usd"] > 0
    acces = client.get(f"/assistant/acces?org_id={monde['ecole'].id}", headers=entetes).json()
    assert acces["autorise"] is True and acces["cout_saison_usd"] == pytest.approx(ligne["cout_usd"], abs=1e-4)


def test_lire_un_fichier(client, monde, monkeypatch):
    ecole = monde["ecole"]
    entetes = {"Authorization": f"Bearer {_en_superuser(client)}", rbac.ENTETE_COMPTE: str(monde["su"].id)}
    base = f"/documents/orgs/{ecole.id}"
    fichier = client.post(
        f"{base}/files", data={"space": "public"}, files={"file": ("Horaires.txt", io.BytesIO(b"Lundi 18h : Jazz"))}, headers=entetes,
    ).json()
    faux = FauxClaude([
        _message(Bloc(type="tool_use", id="t1", name="lire_fichier", input={"fichier_id": fichier["id"]}), stop="tool_use"),
        _message(Bloc(type="text", text="Le Jazz est le lundi à 18 h.")),
    ])
    monkeypatch.setattr(main.assistant_client, "_client", faux)
    client.post(f"/assistant/orgs/{ecole.id}/messages", json={"texte": "Quand est le jazz ?"}, headers=entetes)
    contenu = faux.demandes[1][-1]["content"][0]["content"]
    assert any("Lundi 18h : Jazz" in b.get("text", "") for b in contenu)


def test_reserve_au_superuser(client, monde, monkeypatch):
    monkeypatch.setattr(main.assistant_client, "_client", FauxClaude([]))
    reponse = client.post(
        f"/assistant/orgs/{monde['ecole'].id}/messages", json={"texte": "Bonjour"}, headers=entetes_session(monde["admin"]),
    )
    assert reponse.status_code == 403


def test_la_fiche_d_ecole_du_super_user_y_a_acces(client, db_session, monde, monkeypatch):
    """Même adresse email que le Super User : c'est lui, connecté avec sa fiche d'admin."""
    monkeypatch.setattr(main.assistant_client, "_client", FauxClaude([_message(Bloc(type="text", text="Bonjour."))]))
    seb = Comptes().create(db_session, ecole_id=monde["ecole"].id, role="admin", nom="Richard", prenom="Seb", email="su@test.fr")
    entetes = entetes_session(seb)
    assert client.get("/assistant/acces", headers=entetes).json()["autorise"] is True
    assert client.get("/assistant/acces", headers=entetes_session(monde["admin"])).json()["autorise"] is False
    reponse = client.post(f"/assistant/orgs/{monde['ecole'].id}/messages", json={"texte": "Bonjour"}, headers=entetes)
    assert reponse.status_code == 200 and _evenements(reponse)[-1]["type"] == "fin"


class FauxFichiers:
    def __init__(self):
        self.envoyes = []

    def upload(self, file):
        self.envoyes.append(file[0])
        return SimpleNamespace(id=f"file_envoye_{len(self.envoyes)}")

    def retrieve_metadata(self, file_id):
        return SimpleNamespace(filename="Courbe des inscriptions.pdf")

    def download(self, file_id):
        return SimpleNamespace(read=lambda: b"%PDF-1.7 courbe")


def test_l_ordinateur_fabrique_un_fichier_propose_puis_ajoute(client, monde, monkeypatch):
    ecole = monde["ecole"]
    entetes = {"Authorization": f"Bearer {_en_superuser(client)}", rbac.ENTETE_COMPTE: str(monde["su"].id)}
    base = f"/documents/orgs/{ecole.id}"
    saison = next(e for e in client.get(f"{base}/spaces/private", headers=entetes).json()["items"] if e["system_kind"] == "period")
    chiffres = client.post(
        f"{base}/files", data={"space": "private", "parent_id": str(saison["id"])},
        files={"file": ("Inscriptions.csv", io.BytesIO(b"mois;nombre\nsept;40\noct;52"))}, headers=entetes,
    ).json()
    sortie = Bloc(type="bash_code_execution_output", file_id="file_courbe")
    resultat = Bloc(type="bash_code_execution_tool_result", tool_use_id="srv1",
                    content=Bloc(type="bash_code_execution_result", stdout="", stderr="", return_code=0, content=[sortie]))
    faux = FauxClaude([
        _message(Bloc(type="tool_use", id="t1", name="copier_fichier_dans_l_ordinateur", input={"fichier_id": chiffres["id"]}), stop="tool_use"),
        _message(Bloc(type="server_tool_use", id="srv1", name="bash_code_execution", input={"command": "python courbe.py"}), resultat,
                 Bloc(type="text", text="Voici la courbe.")),
    ])
    faux.files = FauxFichiers()
    monkeypatch.setattr(main.assistant_client, "_client", faux)

    reponse = client.post(
        f"/assistant/orgs/{ecole.id}/messages",
        json={"texte": "Trace la courbe des inscriptions en PDF", "contexte": {"space": "private", "folder_id": saison["id"]}},
        headers=entetes,
    )
    evenements = _evenements(reponse)
    assert "erreur" not in [e["type"] for e in evenements]
    # Le fichier de l'école est copié dans l'ordinateur (container_upload joint au résultat).
    assert faux.files.envoyes == ["Inscriptions.csv"]
    assert {"type": "container_upload", "file_id": "file_envoye_1"} in faux.demandes[1][-1]["content"]
    # Le PDF fabriqué est proposé, rangé dans le dossier regardé.
    carte = next(e for e in evenements if e["type"] == "action")
    assert carte["kind"] == "ajouter_fichier" and carte["nom"] == "Courbe des inscriptions.pdf"
    assert carte["libelle"].startswith("Ajouter « Courbe des inscriptions.pdf » dans Privé › Saison")
    noms = lambda: [e["name"] for e in client.get(f"{base}/spaces/private?folder={saison['id']}", headers=entetes).json()["items"]]
    assert "Courbe des inscriptions.pdf" not in noms()
    # « Faire » : il entre dans Documents, une seule fois.
    url = f"/assistant/orgs/{ecole.id}/produits/{carte['jeton']}"
    corps = {"espace": carte["espace"], "dossier_parent_id": carte["dossier_parent_id"]}
    assert client.post(url, json=corps, headers=entetes).status_code == 200
    assert "Courbe des inscriptions.pdf" in noms()
    assert client.post(url, json=corps, headers=entetes).status_code == 404


def test_fichiers_glisses_dans_l_assistant(client, monde, monkeypatch):
    entetes = {"Authorization": f"Bearer {_en_superuser(client)}", rbac.ENTETE_COMPTE: str(monde["su"].id)}
    faux = FauxClaude([_message(Bloc(type="text", text="Lu."))])
    faux.files = FauxFichiers()
    monkeypatch.setattr(main.assistant_client, "_client", faux)
    url = f"/assistant/orgs/{monde['ecole'].id}"
    note = client.post(f"{url}/pieces", files={"fichier": ("Note.txt", io.BytesIO(b"Gala le 12 juin"))}, headers=entetes).json()
    chiffres = client.post(f"{url}/pieces", files={"fichier": ("Chiffres.csv", io.BytesIO(b"a;b\n1;2"))}, headers=entetes).json()
    assert note["nom"] == "Note.txt" and note["taille"] == 15

    client.post(f"{url}/messages", json={"texte": "Résume", "pieces": [note["id"], chiffres["id"]]}, headers=entetes)
    contenu = faux.demandes[0][0]["content"]
    textes = " ".join(b.get("text", "") for b in contenu)
    assert "Gala le 12 juin" in textes and "Fichier joint « Note.txt »" in textes
    # Les données vont aussi dans l'ordinateur ; la question vient en dernier.
    assert faux.files.envoyes == ["Chiffres.csv"]
    assert {"type": "container_upload", "file_id": "file_envoye_1"} in contenu
    assert contenu[-1]["text"].endswith("Résume")
    # Une pièce ne sert qu'une fois.
    assert note["id"] not in main.assistant_client.pieces


def test_element_de_docs_glisse_dans_l_assistant(client, monde, monkeypatch):
    entetes = {"Authorization": f"Bearer {_en_superuser(client)}", rbac.ENTETE_COMPTE: str(monde["su"].id)}
    faux = FauxClaude([_message(Bloc(type="text", text="Lu."))])
    monkeypatch.setattr(main.assistant_client, "_client", faux)
    url = f"/assistant/orgs/{monde['ecole'].id}"
    docs = f"/documents/orgs/{monde['ecole'].id}"
    saison = next(e for e in client.get(f"{docs}/spaces/private", headers=entetes).json()["items"] if e["system_kind"] == "period")
    fichier = client.post(
        f"{docs}/files", data={"space": "private", "parent_id": str(saison["id"])},
        files={"file": ("Gala.txt", io.BytesIO(b"Gala le 12 juin"))}, headers=entetes,
    ).json()
    client.post(f"{url}/messages", json={"texte": "Résume", "pieces": [f"doc:{fichier['id']}", "doc:999999"]}, headers=entetes)
    textes = " ".join(b.get("text", "") for b in faux.demandes[0][0]["content"])
    assert "Gala le 12 juin" in textes
