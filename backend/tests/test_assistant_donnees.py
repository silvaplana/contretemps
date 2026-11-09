"""Données de l'école pour l'assistant : droits de chacun, et jamais la
santé ni le commentaire libre de l'administration."""

import pytest
from assistant.donnees import OUTILS_DONNEES, DonneesEcole
from comptes import Comptes
from cours import CoursService
from ecoles import Ecoles
from eleves import Eleves
from eleves.models import ProfilEleve
from saisons import portee
from saisons.models import Saison


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


def test_personnes_par_role_avec_le_super_user(db_session, ecole):
    """Seb, 19 octobre : l'assistant connaît toutes les personnes et leurs
    rôles, Super User compris (pour l'ajouter à un groupe)."""
    comptes = Comptes()
    comptes.ajouter_role(db_session, ecole["admin"], "tresorier")
    su = comptes.enregistrer_superuser(db_session, nom="Richard", prenom="Seb", email="seb@test.fr", mot_de_passe_hache="x")
    d = DonneesEcole()
    tous = d.executer(db_session, ecole["admin"], ecole["id"], "lister_personnes", {"role": None})
    assert f"Julia Dho (id {ecole['admin'].id}) : administrateur, trésorier, administrateur principal" in tous
    assert f"Seb Richard (id {su.id}) : Super User" in tous and "Léon Perrin" in tous
    tresoriers = d.executer(db_session, ecole["admin"], ecole["id"], "lister_personnes", {"role": "tresorier"})
    assert "Julia Dho" in tresoriers and "Ima Blanc" not in tresoriers and "Seb Richard" not in tresoriers
    assert d.executer(db_session, ecole["prof"], ecole["id"], "lister_personnes", {"role": None}) == "Réservé aux administrateurs."


def test_infos_ecole_sans_l_iban_entier(db_session, ecole):
    Ecoles().update(db_session, ecole["id"], iban="FR76 3000 6000 0112 3456 7890 189", ville="Toulon")
    texte = DonneesEcole().executer(db_session, ecole["admin"], ecole["id"], "infos_ecole", {})
    assert "Toulon" in texte and "se termine par 0189" in texte and "FR76" not in texte


def test_la_saison_affichee_est_dite_a_l_assistant(db_session, ecole):
    """Seb, 9 novembre : en regardant 2025-2026 (82 élèves), l'assistant
    attribuait ces 82 élèves à 2026-2027, marquée « en cours »."""
    from assistant.donnees import saison_affichee

    courante = db_session.query(Saison).filter_by(ecole_id=ecole["id"]).one()
    ancienne = _ancienne_saison(db_session, ecole["id"])

    assert saison_affichee(db_session, ecole["id"]).startswith(f"Saison affichée : {courante.nom}, la saison en cours.")
    with portee.dans_saison(ancienne.id):
        ligne = saison_affichee(db_session, ecole["id"])
        saisons = DonneesEcole().executer(db_session, ecole["admin"], ecole["id"], "lister_saisons", {})
    assert ligne.startswith(f"Saison affichée : 2010-2011, une ancienne saison (la saison en cours est {courante.nom}).")
    assert "- 2010-2011 : du 2010-09-01 au 2011-08-31 (affichée)" in saisons


def test_l_assistant_lit_une_autre_saison(db_session, ecole):
    """Seb, 9 novembre : « pouvoir interroger toutes les saisons, pas
    seulement la sélectionnée »."""
    ancienne = _ancienne_saison(db_session, ecole["id"])
    with portee.dans_saison(ancienne.id):
        Eleves(comptes=Comptes()).create(db_session, ecole_id=ecole["id"], nom="Vieux", prenom="Paul")
        db_session.commit()
    d = DonneesEcole()

    assert d.executer(db_session, ecole["admin"], ecole["id"], "resume_ecole", {}).startswith("2 élèves")
    autre = d.executer(db_session, ecole["admin"], ecole["id"], "lister_eleves", {"saison": "2010-2011"})
    assert "Vieux" in autre and "Perrin" not in autre
    assert d.executer(db_session, ecole["admin"], ecole["id"], "resume_ecole", {"saison": "1990"}).startswith("Saison inconnue")
    refus = d.executer(db_session, ecole["prof"], ecole["id"], "lister_eleves", {"saison": "2010-2011"})
    assert refus == "Seuls les administrateurs consultent les autres saisons."


def _ancienne_saison(db_session, ecole_id):
    import datetime as dt

    ancienne = Saison(
        ecole_id=ecole_id, nom="2010-2011", date_debut=dt.date(2010, 9, 1), date_fin=dt.date(2011, 8, 31), ouverte=True
    )
    db_session.add(ancienne)
    db_session.commit()
    return ancienne
