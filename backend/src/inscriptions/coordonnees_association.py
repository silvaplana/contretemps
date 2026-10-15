"""Coordonnées de l'association — utilisées par la facture ET le
dossier d'inscription (voir facture_html.py, dossier_html.py). Un seul
endroit à corriger quand les vraies valeurs seront connues.

SIRET/RNA/téléphone : VALEURS PROVISOIRES (décision explicite de
l'utilisateur : mieux vaut un numéro au bon format qu'un évident
"000 000 000 00000", en attendant les vraies valeurs). Adresse et APE
réels.

Depuis le 2026-10-15 (spec §6.1), l'adresse, la ville et le SIRET saisis
dans Admin > École l'emportent : ces valeurs ne servent plus que de repli
quand le champ de l'école est vide (voir `coordonnees`)."""

SIRET = "123 456 789 00012"
APE = "8552Z"
RNA = "W000000000"
TELEPHONE = "04 94 12 34 56"
EMAIL = "contact@dansecontretemps.fr"
SITE = "www.dansecontretemps.fr"
ADRESSE_L1 = "8 impasse des Pivoines"
ADRESSE_L2 = "83330 Le Beausset"
NOM_TRESORIER = "Le Trésorier"


def siret_lisible(siret: str) -> str:
    """« 12345678900012 » -> « 123 456 789 00012 » (3-3-3-5, spec §6.1)."""
    chiffres = "".join(siret.split())
    if len(chiffres) != 14:
        return siret
    return f"{chiffres[:3]} {chiffres[3:6]} {chiffres[6:9]} {chiffres[9:]}"


def coordonnees(ecole) -> dict[str, str]:
    """Adresse (2 lignes) et SIRET à imprimer : ceux de l'école s'ils sont
    saisis, sinon les valeurs ci-dessus — jamais une facture sans adresse."""
    if ecole is None:
        return {"ADRESSE_L1": ADRESSE_L1, "ADRESSE_L2": ADRESSE_L2, "SIRET": SIRET}
    adresse = ", ".join(ligne.strip() for ligne in (ecole.adresse or "").splitlines() if ligne.strip())
    ville = (ecole.ville or "").strip()
    return {
        "ADRESSE_L1": adresse or ADRESSE_L1,
        "ADRESSE_L2": f"{ecole.code_postal} {ville}".strip() if ville else ADRESSE_L2,
        "SIRET": siret_lisible(ecole.siret) if ecole.siret else SIRET,
    }
