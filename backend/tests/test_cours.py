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


def test_supprimer_cours_nettoie_ses_professeurs_et_eleves(client, db_session):
    """`cours_professeurs`/`eleves_cours` sont de simples tables de
    jointure (voir models.py), sans `relationship()` ORM dessus :
    supprimer un cours sans les nettoyer laisse des lignes orphelines qui
    ressurgissent en silence sur un futur cours réutilisant le même id
    (comportement par défaut de SQLite sans mot-clé AUTOINCREMENT) — bug
    repéré lors de tests manuels sur la vraie base de l'école."""
    ecole, prof, eleve = _creer_ecole_et_comptes(db_session)
    creee = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Eveil"}).json()
    client.post(f"/cours/{creee['id']}/professeurs/{prof.id}")
    client.post(f"/cours/{creee['id']}/eleves/{eleve.id}")

    assert client.delete(f"/cours/{creee['id']}").status_code == 204

    nouveau = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Class Ini"}).json()
    assert nouveau["id"] == creee["id"]  # même id réutilisé, comme en pratique avec SQLite
    assert client.get(f"/cours/{nouveau['id']}/professeurs").json() == []
    assert client.get(f"/cours/{nouveau['id']}/eleves").json() == []


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


def test_cours_par_eleve_renvoie_tout_le_mapping_en_un_appel(client, db_session):
    """Version groupée de /eleves/{id}/cours : Admin > Élèves en faisait
    un appel HTTP par ligne, d'où la latence à l'ouverture de l'écran."""
    ecole, _, eleve = _creer_ecole_et_comptes(db_session)
    autre = Comptes().create(db_session, ecole_id=ecole.id, role="eleve", nom="Roux", prenom="Ana")
    c1 = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Éveil"}).json()
    c2 = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Jazz Ini"}).json()
    client.post(f"/cours/{c1['id']}/eleves/{eleve.id}")
    client.post(f"/cours/{c2['id']}/eleves/{eleve.id}")

    reponse = client.get("/cours-par-eleve", params={"ecole_id": ecole.id})
    assert reponse.status_code == 200
    mapping = reponse.json()
    # Clés JSON = chaînes, même pour des identifiants numériques.
    assert mapping[str(eleve.id)] == [c1["id"], c2["id"]]
    # Un élève sans aucun cours est simplement absent du mapping (le
    # frontend retombe sur [], voir frontend/src/api/eleves.js:lister).
    assert str(autre.id) not in mapping


def test_cours_par_eleve_respecte_l_ordre_des_cours(client, db_session):
    """Même ordre que GET /cours (Cours.ordre) : l'affichage doit rester
    identique à celui de l'ancien appel par élève."""
    ecole, _, eleve = _creer_ecole_et_comptes(db_session)
    premier = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Éveil"}).json()
    second = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Jazz"}).json()
    # Inscrit dans l'ordre inverse : c'est bien `ordre` qui doit trancher.
    client.post(f"/cours/{second['id']}/eleves/{eleve.id}")
    client.post(f"/cours/{premier['id']}/eleves/{eleve.id}")

    mapping = client.get("/cours-par-eleve", params={"ecole_id": ecole.id}).json()
    assert mapping[str(eleve.id)] == [premier["id"], second["id"]]


def test_cours_par_eleve_ne_deborde_pas_sur_une_autre_ecole(client, db_session):
    ecole, _, eleve = _creer_ecole_et_comptes(db_session)
    cours = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Éveil"}).json()
    client.post(f"/cours/{cours['id']}/eleves/{eleve.id}")

    voisine = Ecoles().create(db_session, nom="Voisine", code_postal="83000")
    eleve_voisin = Comptes().create(
        db_session, ecole_id=voisine.id, role="eleve", nom="Blanc", prenom="Ima"
    )
    cours_voisin = client.post(
        "/cours", params={"ecole_id": voisine.id}, json={"nom": "Éveil"}
    ).json()
    client.post(f"/cours/{cours_voisin['id']}/eleves/{eleve_voisin.id}")

    mapping = client.get("/cours-par-eleve", params={"ecole_id": ecole.id}).json()
    assert list(mapping) == [str(eleve.id)]


def test_professeurs_par_cours_renvoie_tout_le_mapping_en_un_appel(client, db_session):
    ecole, prof, _ = _creer_ecole_et_comptes(db_session)
    avec = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Éveil"}).json()
    sans = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Jazz Ini"}).json()
    client.post(f"/cours/{avec['id']}/professeurs/{prof.id}")

    reponse = client.get("/professeurs-par-cours", params={"ecole_id": ecole.id})
    assert reponse.status_code == 200
    mapping = reponse.json()
    assert mapping[str(avec["id"])] == [prof.id]
    assert str(sans["id"]) not in mapping


def test_cours_par_eleve_expose_les_inscriptions_sans_profil_eleve(client, db_session):
    """Cas vu en production : 2 comptes inscrits à des cours mais sans
    profil d'élève, donc absents de GET /eleves (qui les saute, voir
    eleves/receiver.py:lister). Le mapping les expose — sans conséquence,
    les écrans itèrent sur la liste d'élèves et ignorent ces clés. Test
    de constat : si ce comportement change un jour, c'est délibéré."""
    ecole, prof, _ = _creer_ecole_et_comptes(db_session)
    cours = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Éveil"}).json()
    # Un prof n'a pas de profil d'élève : il tient le rôle du compte
    # orphelin, sans avoir à fabriquer une base incohérente à la main.
    client.post(f"/cours/{cours['id']}/eleves/{prof.id}")

    assert client.get(f"/eleves/{prof.id}").status_code == 404
    mapping = client.get("/cours-par-eleve", params={"ecole_id": ecole.id}).json()
    assert mapping[str(prof.id)] == [cours["id"]]

    # Ce que voit vraiment l'écran : rien, puisqu'il boucle sur /eleves.
    ids_affiches = [e["id"] for e in client.get("/eleves", params={"ecole_id": ecole.id}).json()]
    assert prof.id not in ids_affiches


def test_routes_groupees_ne_masquent_pas_cours_par_id(client, db_session):
    """/cours-par-eleve et /cours/{cours_id} cohabitent : le chemin sans
    paramètre a été choisi exprès pour éviter ce conflit de routage."""
    ecole, _, _ = _creer_ecole_et_comptes(db_session)
    cours = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Éveil"}).json()
    assert client.get(f"/cours/{cours['id']}").json()["nom"] == "Éveil"
    assert client.get("/cours-par-eleve", params={"ecole_id": ecole.id}).status_code == 200
