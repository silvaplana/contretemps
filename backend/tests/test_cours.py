"""Tests du module cours (voir spec/SPEC.md §6.5)."""

from comptes import Comptes
from ecoles import Ecoles


def _creer_ecole_et_comptes(db_session):
    ecoles = Ecoles()
    comptes = Comptes()
    ecole = ecoles.create(db_session, nom="Contretemps", code_postal="83330")
    prof = comptes.create(
        db_session, ecole_id=ecole.id, role="professeur", nom="Pesenti", prenom="Marie-Laure"
    )
    eleve = comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="Perrin", prenom="Léon")
    return ecole, prof, eleve


def test_creer_puis_lister(client, db_session):
    ecole, _, _ = _creer_ecole_et_comptes(db_session)
    reponse = client.post(
        "/cours",
        params={"ecole_id": ecole.id},
        json={"nom": "Eveil", "jour": "Mercredi", "heure_debut": "17:00", "heure_fin": "18:00"},
    )
    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["nom"] == "Eveil"
    assert corps["ecole_id"] == ecole.id

    reponse = client.get("/cours", params={"ecole_id": ecole.id})
    assert reponse.status_code == 200
    assert len(reponse.json()) == 1


def test_lister_respecte_l_ordre_pas_l_alphabetique(client, db_session):
    """Voir models.py:Cours.ordre — un nouveau cours va à la fin (jamais
    trié alphabétiquement, "Éveil" doit rester avant "Class Ini")."""
    ecole, _, _ = _creer_ecole_et_comptes(db_session)
    client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Éveil"})
    client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Class Ini"})
    client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Ateliers"})

    noms = [c["nom"] for c in client.get("/cours", params={"ecole_id": ecole.id}).json()]
    assert noms == ["Éveil", "Class Ini", "Ateliers"]


def test_modifier_ordre(client, db_session):
    ecole, _, _ = _creer_ecole_et_comptes(db_session)
    c1 = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "A"}).json()
    c2 = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "B"}).json()
    assert c1["ordre"] < c2["ordre"]

    client.put(f"/cours/{c1['id']}", json={"ordre": c2["ordre"] + 1})
    noms = [c["nom"] for c in client.get("/cours", params={"ecole_id": ecole.id}).json()]
    assert noms == ["B", "A"]


def test_modifier_cours(client, db_session):
    ecole, _, _ = _creer_ecole_et_comptes(db_session)
    creee = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Eveil"}).json()
    reponse = client.put(f"/cours/{creee['id']}", json={"salle": "Salle 1"})
    assert reponse.status_code == 200
    assert reponse.json()["salle"] == "Salle 1"
    assert reponse.json()["nom"] == "Eveil"


def test_supprimer_cours(client, db_session):
    ecole, _, _ = _creer_ecole_et_comptes(db_session)
    creee = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Eveil"}).json()
    assert client.delete(f"/cours/{creee['id']}").status_code == 204
    assert client.get(f"/cours/{creee['id']}").status_code == 404


def test_cours_introuvable(client):
    assert client.get("/cours/999").status_code == 404
    assert client.put("/cours/999", json={"nom": "X"}).status_code == 404
    assert client.delete("/cours/999").status_code == 404


def test_ajouter_et_retirer_professeur(client, db_session):
    ecole, prof, _ = _creer_ecole_et_comptes(db_session)
    creee = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Eveil"}).json()

    assert client.post(f"/cours/{creee['id']}/professeurs/{prof.id}").status_code == 204
    reponse = client.get(f"/cours/{creee['id']}/professeurs")
    assert reponse.status_code == 200
    assert [p["id"] for p in reponse.json()] == [prof.id]

    assert client.delete(f"/cours/{creee['id']}/professeurs/{prof.id}").status_code == 204
    assert client.get(f"/cours/{creee['id']}/professeurs").json() == []


def test_inscrire_et_desinscrire_eleve(client, db_session):
    ecole, _, eleve = _creer_ecole_et_comptes(db_session)
    creee = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Eveil"}).json()

    assert client.post(f"/cours/{creee['id']}/eleves/{eleve.id}").status_code == 204
    reponse = client.get(f"/cours/{creee['id']}/eleves")
    assert reponse.status_code == 200
    assert [e["id"] for e in reponse.json()] == [eleve.id]

    assert client.delete(f"/cours/{creee['id']}/eleves/{eleve.id}").status_code == 204
    assert client.get(f"/cours/{creee['id']}/eleves").json() == []


def test_inscrire_eleve_deux_fois_ne_duplique_pas(client, db_session):
    ecole, _, eleve = _creer_ecole_et_comptes(db_session)
    creee = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Eveil"}).json()

    client.post(f"/cours/{creee['id']}/eleves/{eleve.id}")
    client.post(f"/cours/{creee['id']}/eleves/{eleve.id}")
    assert len(client.get(f"/cours/{creee['id']}/eleves").json()) == 1


def test_creer_avec_horaires_supplementaires(client, db_session):
    """Rare (voir models.py:Cours.horaires_supplementaires) : un cours
    proposé plusieurs jours, ex. "Éveil" le lundi ET le mercredi."""
    ecole, _, _ = _creer_ecole_et_comptes(db_session)
    reponse = client.post(
        "/cours",
        params={"ecole_id": ecole.id},
        json={
            "nom": "Éveil",
            "jour": "Mercredi",
            "heure_debut": "17:00",
            "heure_fin": "17:45",
            "horaires_supplementaires": [
                {"jour": "Lundi", "heure_debut": "17:15", "heure_fin": "18:00"}
            ],
        },
    )
    assert reponse.status_code == 201
    corps = reponse.json()
    assert len(corps["horaires_supplementaires"]) == 1
    assert corps["horaires_supplementaires"][0]["jour"] == "Lundi"

    relu = client.get(f"/cours/{corps['id']}").json()
    assert relu["horaires_supplementaires"][0]["heure_debut"] == "17:15"


def test_cours_sans_horaires_supplementaires_liste_vide(client, db_session):
    ecole, _, _ = _creer_ecole_et_comptes(db_session)
    creee = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Eveil"}).json()
    assert creee["horaires_supplementaires"] == []


def test_modifier_horaires_supplementaires_remplace_la_liste(client, db_session):
    ecole, _, _ = _creer_ecole_et_comptes(db_session)
    creee = client.post(
        "/cours",
        params={"ecole_id": ecole.id},
        json={
            "nom": "Éveil",
            "horaires_supplementaires": [
                {"jour": "Lundi", "heure_debut": "17:15", "heure_fin": "18:00"}
            ],
        },
    ).json()

    # Remplace par un autre créneau.
    reponse = client.put(
        f"/cours/{creee['id']}",
        json={
            "horaires_supplementaires": [
                {"jour": "Samedi", "heure_debut": "10:00", "heure_fin": "10:45"}
            ]
        },
    )
    assert reponse.status_code == 200
    horaires = reponse.json()["horaires_supplementaires"]
    assert len(horaires) == 1
    assert horaires[0]["jour"] == "Samedi"

    # Ne pas fournir le champ ne touche pas aux créneaux existants.
    reponse2 = client.put(f"/cours/{creee['id']}", json={"salle": "Salle 2"})
    assert len(reponse2.json()["horaires_supplementaires"]) == 1

    # Une liste vide les supprime tous.
    reponse3 = client.put(f"/cours/{creee['id']}", json={"horaires_supplementaires": []})
    assert reponse3.json()["horaires_supplementaires"] == []


def test_supprimer_cours_supprime_ses_horaires_supplementaires(client, db_session):
    ecole, _, _ = _creer_ecole_et_comptes(db_session)
    creee = client.post(
        "/cours",
        params={"ecole_id": ecole.id},
        json={
            "nom": "Éveil",
            "horaires_supplementaires": [
                {"jour": "Lundi", "heure_debut": "17:15", "heure_fin": "18:00"}
            ],
        },
    ).json()
    assert client.delete(f"/cours/{creee['id']}").status_code == 204
    # Pas d'erreur d'intégrité (cascade, voir models.py) — vérifié
    # indirectement : recréer un cours du même nom fonctionne toujours.
    reponse = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Éveil"})
    assert reponse.status_code == 201


def test_creer_modifier_supprimer_publient_cours_maj_a_toute_lecole(client, db_session):
    """Demande utilisateur du 2026-09-19 : le sélecteur de cours (voir
    frontend/src/components/Header.jsx) doit se tenir à jour en direct —
    création, modification ET suppression préviennent TOUS les comptes
    de l'école (admin/profs/élèves n'ont pas les mêmes cours visibles,
    voir App.jsx: coursDuProfil — filtré côté client, pas ici)."""
    from app.main import evenements_client

    ecole, prof, eleve = _creer_ecole_et_comptes(db_session)
    queue_prof = evenements_client.abonner(prof.id)
    queue_eleve = evenements_client.abonner(eleve.id)
    try:
        cours = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Eveil"}).json()
        assert queue_prof.get_nowait() == {"type": "cours_maj"}
        assert queue_eleve.get_nowait() == {"type": "cours_maj"}

        client.put(f"/cours/{cours['id']}", json={"nom": "Eveil bis"})
        assert queue_prof.get_nowait() == {"type": "cours_maj"}
        assert queue_eleve.get_nowait() == {"type": "cours_maj"}

        client.delete(f"/cours/{cours['id']}")
        assert queue_prof.get_nowait() == {"type": "cours_maj"}
        assert queue_eleve.get_nowait() == {"type": "cours_maj"}
    finally:
        evenements_client.desabonner(prof.id, queue_prof)
        evenements_client.desabonner(eleve.id, queue_eleve)


def test_inscription_et_professeur_publient_cours_maj(client, db_session):
    """Un changement d'inscription (élève ajouté/retiré) ou de
    professeur affecte qui voit ce cours (voir App.jsx: coursDuProfil) —
    doit prévenir en direct comme une modification du cours lui-même."""
    from app.main import evenements_client

    ecole, prof, eleve = _creer_ecole_et_comptes(db_session)
    cours = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Eveil"}).json()

    queue_eleve = evenements_client.abonner(eleve.id)
    try:
        client.post(f"/cours/{cours['id']}/eleves/{eleve.id}")
        assert queue_eleve.get_nowait() == {"type": "cours_maj"}

        client.delete(f"/cours/{cours['id']}/eleves/{eleve.id}")
        assert queue_eleve.get_nowait() == {"type": "cours_maj"}

        client.post(f"/cours/{cours['id']}/professeurs/{prof.id}")
        assert queue_eleve.get_nowait() == {"type": "cours_maj"}

        client.delete(f"/cours/{cours['id']}/professeurs/{prof.id}")
        assert queue_eleve.get_nowait() == {"type": "cours_maj"}
    finally:
        evenements_client.desabonner(eleve.id, queue_eleve)


def test_cours_de_leleve(client, db_session):
    """Sens inverse de /cours/{id}/eleves — voir Admin > Élèves (colonne
    "cours suivis")."""
    ecole, _, eleve = _creer_ecole_et_comptes(db_session)
    c1 = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Eveil"}).json()
    c2 = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Jazz"}).json()
    client.post(f"/cours/{c1['id']}/eleves/{eleve.id}")

    reponse = client.get(f"/eleves/{eleve.id}/cours")
    assert reponse.status_code == 200
    assert [c["id"] for c in reponse.json()] == [c1["id"]]
    assert c2["id"] not in [c["id"] for c in reponse.json()]
