"""Données de l'école pour l'assistant : droits de chacun, et jamais la
santé ni le commentaire libre de l'administration."""

import pytest
from assistant.donnees import OUTILS_DONNEES, DonneesEcole
from comptes import Comptes
from cours import CoursService
from ecoles import Ecoles
from eleves import Eleves
from eleves.models import ProfilEleve


@pytest.fixture()
def ecole(db_session):
    comptes = Comptes()
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    admin = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia")
    prof = comptes.create(db_session, ecole_id=ecole.id, role="professeur", nom="Blanc", prenom="Ima")
    leon, _ = Eleves(comptes=comptes).create(db_session, ecole_id=ecole.id, nom="Perrin", prenom="Léon")
    ana, _ = Eleves(comptes=comptes).create(db_session, ecole_id=ecole.id, nom="Roux", prenom="Ana")
    eveil = CoursService().create(db_session, ecole_id=ecole.id, nom="Éveil")
    CoursService().inscrire_eleve(db_session, eveil.id, leon.id)
    CoursService().ajouter_professeur(db_session, eveil.id, prof.id)
    for eleve in (leon, ana):
        profil = db_session.query(ProfilEleve).filter_by(compte_id=eleve.id).first()
        profil.allergies = "ARACHIDES-SECRET"
        profil.traitement_medical = "VENTOLINE-SECRET"
        profil.commentaire_admin = "COMMENTAIRE-SECRET"
        profil.montant_total_annee, profil.montant_paye = 300, 100
    db_session.commit()
    return {"id": ecole.id, "admin": admin, "prof": prof, "leon": leon, "ana": ana, "eveil": eveil}


def _tout(db_session, compte, ecole_id, eleve_id):
    d = DonneesEcole()
    sorties = []
    for outil in OUTILS_DONNEES:
        args = {k: None for k in outil["input_schema"]["properties"]}
        if outil["name"] == "fiche_eleve":
            args = {"eleve_id": eleve_id}
        sorties.append(d.executer(db_session, compte, ecole_id, outil["name"], args))
    return "\n".join(sorties)


def test_jamais_la_sante_commentaire_pour_les_admins_seulement(db_session, ecole):
    texte = _tout(db_session, ecole["admin"], ecole["id"], ecole["leon"].id)
    assert "Léon Perrin" in texte and "Ana Roux" in texte and "100/300 €" in texte
    for secret in ("ARACHIDES", "VENTOLINE"):
        assert secret not in texte
    # Le commentaire de l'administration : aux admins et au Super User
    # seulement (Seb, 16 octobre).
    assert "COMMENTAIRE-SECRET" in texte
    texte_prof = _tout(db_session, ecole["prof"], ecole["id"], ecole["leon"].id)
    for secret in ("ARACHIDES", "VENTOLINE", "COMMENTAIRE-SECRET"):
        assert secret not in texte_prof


def test_le_prof_ne_voit_que_ses_cours_sans_paiements(db_session, ecole):
    d = DonneesEcole()
    eleves = d.executer(db_session, ecole["prof"], ecole["id"], "lister_eleves", {"cours_id": None, "nom": None, "statut_paiement": None})
    assert "Léon Perrin" in eleves and "Ana Roux" not in eleves and "€" not in eleves
    # Pas de fiche élève pour un prof (Seb, 16 octobre : pas plus que ses écrans).
    assert d.executer(db_session, ecole["prof"], ecole["id"], "fiche_eleve", {"eleve_id": ecole["leon"].id}) == "Réservé aux administrateurs."
    assert d.executer(db_session, ecole["prof"], ecole["id"], "lister_professeurs", {}) == "Réservé aux administrateurs."


def test_l_eleve_ne_voit_que_lui(db_session, ecole):
    d = DonneesEcole()
    eleves = d.executer(db_session, ecole["leon"], ecole["id"], "lister_eleves", {"cours_id": None, "nom": None, "statut_paiement": None})
    assert "Léon Perrin" in eleves and "Ana Roux" not in eleves
