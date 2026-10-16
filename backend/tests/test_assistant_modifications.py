"""Modifications proposées par l'assistant : vérifiées et décrites par le
serveur, faites seulement après validation, ligne par ligne."""

import pytest
from assistant.modifications import Modifications, Refus
from choregraphies import Choregraphies
from comptes import Comptes
from cours import CoursService
from ecoles import Ecoles
from eleves import Eleves
from eleves.models import ProfilEleve
from presence import Presence
from presence.models import PresenceEleve
from videos import Videos


@pytest.fixture()
def monde(db_session):
    comptes = Comptes()
    cours_service = CoursService()
    eleves = Eleves(comptes=comptes)
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    autre = Ecoles().create(db_session, nom="Ailleurs", code_postal="75000")
    admin = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia")
    prof = comptes.create(db_session, ecole_id=ecole.id, role="professeur", nom="Blanc", prenom="Ima")
    leon, _ = eleves.create(db_session, ecole_id=ecole.id, nom="Perrin", prenom="Léon")
    etranger, _ = eleves.create(db_session, ecole_id=autre.id, nom="Loin", prenom="Max")
    eveil = cours_service.create(db_session, ecole_id=ecole.id, nom="Éveil")
    cours_service.inscrire_eleve(db_session, eveil.id, leon.id)
    cours_service.ajouter_professeur(db_session, eveil.id, prof.id)
    profil = db_session.query(ProfilEleve).filter_by(compte_id=leon.id).first()
    profil.montant_total_annee, profil.montant_paye = 300, 250
    db_session.commit()
    m = Modifications(
        eleves=eleves, comptes=comptes, cours=cours_service, presence=Presence(cours=cours_service),
        choregraphies=Choregraphies(cours=cours_service, videos=Videos()),
    )
    return {"m": m, "ecole": ecole.id, "admin": admin, "prof": prof, "leon": leon, "etranger": etranger, "eveil": eveil}


def test_proposer_puis_faire_les_lignes_cochees(db_session, monde):
    m, e = monde["m"], monde["ecole"]
    texte, carte = m.proposer(db_session, monde["admin"], e, 1, {"titre": "Essai", "changements": [
        {"type": "noter_paiement", "eleve_id": monde["leon"].id, "montant": 50},
        {"type": "presence_eleve", "cours_id": monde["eveil"].id, "eleve_id": monde["leon"].id, "date": "2026-10-14", "statut": "absent"},
        {"type": "modifier_cours", "cours_id": monde["eveil"].id, "champs": {"salle": "Salle 2"}},
        {"type": "modifier_eleve", "eleve_id": monde["etranger"].id, "champs": {"telephone": "06"}},
        {"type": "modifier_eleve", "eleve_id": monde["leon"].id, "champs": {"allergies": "x"}},
    ]})
    assert carte["kind"] == "modifications" and len(carte["lignes"]) == 3
    assert "paiement de 50 € (payé 250 → 300 € sur 300 €)" in carte["lignes"][0]
    assert "Refusés" in texte and "introuvable" in texte and "non modifiable" in texte
    # Rien n'est fait avant la validation.
    assert db_session.query(PresenceEleve).count() == 0

    # Comme en vrai : la validation arrive dans une autre requête.
    db_session.expunge_all()
    admin = db_session.get(type(monde["admin"]), monde["admin"].id)
    resultats = m.executer(db_session, admin, e, 1, carte["jeton"], [0, 1])
    assert [r["ok"] for r in resultats] == [True, True]
    profil = db_session.query(ProfilEleve).filter_by(compte_id=monde["leon"].id).first()
    assert profil.montant_paye == 300 and profil.statut_paiement == "paye"
    assert db_session.query(PresenceEleve).one().statut == "absent"
    from cours.models import Cours

    assert db_session.get(Cours, monde["eveil"].id).salle != "Salle 2"  # décochée
    # Une proposition ne sert qu'une fois.
    with pytest.raises(Refus):
        m.executer(db_session, admin, e, 1, carte["jeton"], [2])


def test_reserve_aux_administrateurs(db_session, monde):
    texte, carte = monde["m"].proposer(db_session, monde["prof"], monde["ecole"], 2, {"titre": "x", "changements": [
        {"type": "modifier_cours", "cours_id": monde["eveil"].id, "champs": {"salle": "B"}},
    ]})
    assert carte is None and "réservé aux administrateurs" in texte


def test_creations_et_heures(db_session, monde):
    m, e, eveil = monde["m"], monde["ecole"], monde["eveil"]
    _, carte = m.proposer(db_session, monde["admin"], e, 1, {"titre": "x", "changements": [
        {"type": "creer_eleve", "nom": "Roux", "prenom": "Ana", "champs": {"telephone": "0600"}, "cours_ids": [eveil.id]},
        {"type": "creer_choregraphie", "cours_id": eveil.id, "champs": {"nom": "Gala", "costume": "Rouge"}, "eleve_ids": [monde["leon"].id]},
        {"type": "heures_professeur", "cours_id": eveil.id, "professeur_id": monde["prof"].id, "date": "2026-10-14",
         "champs": {"heure_fin_reelle": "18:10", "depassement_minutes": 10}},
    ]})
    assert len(carte["lignes"]) == 3
    admin_id = monde["admin"].id
    db_session.expunge_all()
    resultats = m.executer(db_session, db_session.get(type(monde["admin"]), admin_id), e, 1, carte["jeton"], [0, 1, 2])
    assert all(r["ok"] for r in resultats), resultats
    from comptes.models import Compte

    ana = db_session.query(Compte).filter_by(prenom="Ana").one()
    assert ana.telephone == "0600"
    assert [c.nom for c in CoursService().cours_de_leleve(db_session, ana.id)] == ["Éveil"]
