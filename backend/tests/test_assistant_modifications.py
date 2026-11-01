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


def test_commentaire_et_rouge_par_le_super_user(db_session, monde):
    """Seb, 16 octobre : le Super User (comme un admin) lit et modifie le
    commentaire de l'administration et met un élève en rouge par le chat."""
    from assistant.donnees import DonneesEcole
    from securite import mots_de_passe

    su = Comptes().enregistrer_superuser(
        db_session, nom="Richard", prenom="Sébastien", email="su@test.fr", mot_de_passe_hache=mots_de_passe.hacher("x" * 12),
    )
    m, e, leon = monde["m"], monde["ecole"], monde["leon"]
    texte, carte = m.proposer(db_session, su, e, 9, {"titre": "Léon", "changements": [
        {"type": "modifier_eleve", "eleve_id": leon.id, "champs": {
            "commentaire_admin": "Rappeler la maman", "ligne_rouge": True, "cellules_rouges": ["paiement"],
        }},
        {"type": "modifier_eleve", "eleve_id": leon.id, "champs": {"cellules_rouges": ["inconnue"]}},
    ]})
    assert carte["lignes"] == ["Léon Perrin : commentaire vide → Rappeler la maman, en rouge non → oui, colonnes en rouge vide → paiement"]
    assert "cellules_rouges" in texte  # la colonne inconnue est refusée
    m.executer(db_session, su, e, 9, carte["jeton"], [0])
    profil = db_session.query(ProfilEleve).filter_by(compte_id=leon.id).first()
    assert profil.commentaire_admin == "Rappeler la maman" and profil.ligne_rouge is True and profil.cellules_rouges == ["paiement"]

    fiche = DonneesEcole().executer(db_session, su, e, "fiche_eleve", {"eleve_id": leon.id})
    assert "Commentaire de l'administration : Rappeler la maman" in fiche
    assert "En rouge dans Admin > Élèves : toute la ligne, paiement" in fiche
    # Le professeur ne voit ni le commentaire ni le rouge.
    fiche_prof = DonneesEcole().executer(db_session, monde["prof"], e, "fiche_eleve", {"eleve_id": leon.id})
    assert "Rappeler" not in fiche_prof and "rouge" not in fiche_prof


def test_choregraphie_sur_plusieurs_cours(db_session, monde):
    """Seb, 1er novembre : une chorégraphie peut être dansée par plusieurs cours."""
    from assistant.donnees import DonneesEcole

    m, e, eveil = monde["m"], monde["ecole"], monde["eveil"]
    adultes = CoursService().create(db_session, ecole_id=e, nom="Contempo Adulte")
    _, carte = m.proposer(db_session, monde["admin"], e, 1, {"titre": "x", "changements": [
        {"type": "creer_choregraphie", "cours_id": eveil.id, "champs": {"nom": "Begging you"}, "cours_ids": [adultes.id]},
    ]})
    assert carte["lignes"] == ["Nouvelle chorégraphie « Begging you » (Éveil, Contempo Adulte)"]
    m.executer(db_session, monde["admin"], e, 1, carte["jeton"], [0])
    texte = DonneesEcole().executer(db_session, monde["admin"], e, "lister_choregraphies", {"cours_id": adultes.id})
    assert texte.startswith("- Begging you (Éveil, Contempo Adulte)")

    ch_id = m.choregraphies.list(db_session, adultes.id)[0].id
    _, carte = m.proposer(db_session, monde["admin"], e, 1, {"titre": "x", "changements": [
        {"type": "modifier_choregraphie", "choregraphie_id": ch_id, "cours_ids": [adultes.id]},
    ]})
    assert carte["lignes"] == ["Chorégraphie « Begging you » (Éveil, Contempo Adulte) : cours : Contempo Adulte"]
    m.executer(db_session, monde["admin"], e, 1, carte["jeton"], [0])
    assert m.choregraphies.list(db_session, eveil.id) == []
