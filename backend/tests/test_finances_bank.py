"""Connexion bancaire du Financier (finances/bank.py, spec financier.md §3.5),
contre un faux Enable Banking : banque choisie par organisation, n comptes,
comptes créés depuis l'IBAN, opérations provisoires, relevé qui fait foi."""

import datetime as dt

import pytest
from test_finances import COURANT, TRESORIER, AUTRE_ECOLE, make_statement

from finances import Finances
from finances.bank import Bank, BankError
from finances.models import FinBankConnection

AUJOURDHUI = dt.date.today()
JOUR = lambda n: (AUJOURDHUI - dt.timedelta(days=n)).isoformat()  # noqa: E731
# Trois comptes de la même agence : 401 et 403 courants, 402 livret.
IBAN = {n: f"FR761027800000000204614{n}76" for n in ("401", "402", "403")}


def compte(uid, iban, product):
    return {"uid": uid, "account_id": {"iban": iban}, "product": product, "cash_account_type": "SVGS" if "Livret" in product else "CACC"}


class FauxEnableBanking:
    def __init__(self, comptes=None, operations=None, soldes=None):
        self.demandes = []
        self.comptes = comptes or [
            compte("u401", IBAN["401"], "Compte courant"),
            compte("u402", IBAN["402"], "Livret A"),
            compte("u403", IBAN["403"], "Compte courant"),
            {"uid": "carte", "product": "Carte"},  # sans IBAN : jamais suivie
        ]
        self.operations = operations or {
            "u401": [("VIR HELLOASSO ADHESIONS", 612.00, 3), ("PRLV EDF", -84.35, 2)],
            "u402": [],
            "u403": [("VIR HONORAIRES MARIE", -450.00, 1)],
        }
        self.soldes = soldes or {"u401": 4823.17, "u402": 12500.00, "u403": 900.00}
        self.lus = []

    def list_banks(self, country):
        return [{"name": "CIC", "country": "FR", "psu_types": ["personal", "business"]}, {"name": "BoursoBank", "country": "FR", "psu_types": ["personal"]}]

    def start_authorization(self, state, bank, country, psu_type):
        self.demandes.append({"state": state, "bank": bank, "country": country, "psu_type": psu_type})
        return f"https://banque.exemple/auth?state={state}"

    def create_session(self, code):
        assert code == "code-ok"
        fin = (dt.datetime.now(dt.UTC) + dt.timedelta(days=179)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {"session_id": "sess-1", "access": {"valid_until": fin}, "accounts": self.comptes}

    def get_balances(self, uid):
        self.lus.append(uid)
        return [{"balance_type": "CLBD", "balance_amount": {"amount": str(self.soldes[uid])}}]

    def get_transactions(self, uid, date_from, continuation_key=None):
        return {
            "transactions": [
                {
                    "transaction_amount": {"amount": str(abs(m)), "currency": "EUR"},
                    "credit_debit_indicator": "DBIT" if m < 0 else "CRDT",
                    "remittance_information": [libelle],
                    "booking_date": JOUR(n),
                }
                for libelle, m, n in self.operations[uid]
            ]
        }


@pytest.fixture
def faux():
    return FauxEnableBanking()


@pytest.fixture
def banque(faux):
    return Bank(client=faux, finances=Finances(), encrypt=lambda s: f"chiffre:{s}", decrypt=lambda s: s.removeprefix("chiffre:"))


def connecter(banque, faux, db, membre=TRESORIER, bank="CIC", psu="business"):
    url = banque.connect(db, membre, bank, psu)
    state = faux.demandes[-1]["state"]
    assert url.endswith(state)
    return banque.complete(db, "code-ok", state)


def test_connexion_et_n_comptes(banque, faux, db_session):
    assert connecter(banque, faux, db_session) == TRESORIER.org_id
    assert faux.demandes[-1] == {"state": faux.demandes[-1]["state"], "bank": "CIC", "country": "FR", "psu_type": "business"}
    statut = banque.status(db_session, TRESORIER)
    assert statut["connected"] and statut["bank"] == "CIC" and statut["psuType"] == "business"
    # La carte (sans IBAN) n'est pas proposée ; les trois comptes sont suivis.
    assert [(a["name"], a["iban"], a["followed"]) for a in statut["accounts"]] == [
        ("Compte courant 401", "•••• 0176", True), ("Livret A 402", "•••• 0276", True), ("Compte courant 403", "•••• 0376", True),
    ]
    # Session chiffrée en base.
    assert db_session.query(FinBankConnection).one().session_encrypted == "chiffre:sess-1"

    # Comptes créés depuis l'IBAN, soldes de la banque, opérations provisoires.
    ledger = Finances().get_ledger(db_session, TRESORIER)
    soldes = {a["name"]: a["balance"] for a in ledger["accounts"]}
    assert soldes == {"Compte courant 401": 4823.17, "Compte courant 403": 900.0, "Livret A 402": 12500.0}
    assert ledger["total"] == 18223.17
    assert all(r["provisional"] for r in ledger["rows"]) and len(ledger["rows"]) == 3
    # Le solde de chaque ligne retombe sur le solde de la banque.
    assert ledger["rows"][0]["total"] == 18223.17

    # Renommer les comptes.
    ids = {a["name"]: a["id"] for a in ledger["accounts"]}
    Finances().rename_account(db_session, TRESORIER, ids["Compte courant 403"], "Honoraires profs")
    noms = [a["name"] for a in Finances().get_ledger(db_session, TRESORIER)["accounts"]]
    assert "Honoraires profs" in noms


def test_actualiser_deux_fois_n_ajoute_rien(banque, faux, db_session):
    connecter(banque, faux, db_session)
    assert banque.sync(db_session, TRESORIER) == {"added": 0}
    faux.operations["u401"].append(("CB DECATHLON", -129.90, 0))
    assert banque.sync(db_session, TRESORIER) == {"added": 1}
    assert len(Finances().get_ledger(db_session, TRESORIER)["rows"]) == 4


def test_comptes_suivis(banque, faux, db_session):
    connecter(banque, faux, db_session)
    banque.follow(db_session, TRESORIER, ["u401"])
    faux.lus.clear()
    banque.sync(db_session, TRESORIER)
    assert faux.lus == ["u401"]


def test_le_releve_fait_foi(faux, db_session):
    """Un compte déjà importé par relevé est reconnu à son numéro dans
    l'IBAN ; le relevé suivant efface les opérations provisoires qu'il couvre."""
    finances = Finances()
    finances.import_files(db_session, TRESORIER, [("c1.pdf", make_statement(COURANT, ("30/06/2024", 100000), [("03/07/2024", "CB DECATHLON", -20000, [])], "31/07/2024"))])
    iban = "FR761027800000000020461601" + "76"
    faux.comptes = [compte("u1", iban, "Compte courant")]
    faux.operations = {"u1": [("VIR HELLOASSO", 100.0, 5)]}
    faux.soldes = {"u1": 900.0}
    banque = Bank(client=faux, finances=finances, encrypt=str, decrypt=str)
    connecter(banque, faux, db_session)
    ledger = finances.get_ledger(db_session, TRESORIER)
    assert len(ledger["accounts"]) == 1 and ledger["accounts"][0]["name"] == "Compte courant"
    assert [r["provisional"] for r in ledger["rows"]] == [True, False]
    # Le relevé qui couvre l'opération provisoire arrive : elle s'efface.
    debut = dt.date.today() - dt.timedelta(days=40)
    fin = dt.date.today()
    releve = make_statement(
        COURANT, (debut.strftime("%d/%m/%Y"), 80000), [(JOUR(5)[8:10] + "/" + JOUR(5)[5:7] + "/" + JOUR(5)[:4], "VIR HELLOASSO", 10000, [])], fin.strftime("%d/%m/%Y"),
    )
    finances.import_files(db_session, TRESORIER, [("c2.pdf", releve)])
    ledger = finances.get_ledger(db_session, TRESORIER)
    assert [r["provisional"] for r in ledger["rows"]] == [False, False]


def test_retour_inconnu_et_etancheite(banque, faux, db_session):
    with pytest.raises(BankError):
        banque.complete(db_session, "code-ok", "inconnu")
    connecter(banque, faux, db_session)
    # L'autre école ne voit ni la connexion ni les comptes.
    assert banque.status(db_session, AUTRE_ECOLE)["connected"] is False
    assert Finances().get_ledger(db_session, AUTRE_ECOLE)["accounts"] == []
    with pytest.raises(BankError):
        banque.sync(db_session, AUTRE_ECOLE)


def test_sans_cle_sur_le_serveur(db_session):
    sans = Bank(client=None, finances=Finances(), encrypt=str, decrypt=str)
    assert sans.status(db_session, TRESORIER)["configured"] is False
    with pytest.raises(BankError):
        sans.connect(db_session, TRESORIER, "CIC")


@pytest.mark.rbac_reel
def test_routes_et_retour_de_la_banque(client, db_session, monkeypatch):
    """Le retour de la banque est public (protégé par `state`) et renvoie vers
    l'adresse de l'école ; le reste est réservé aux trésoriers."""
    from conftest import entetes_session

    from app import main
    from comptes import Comptes, roles
    from ecoles import Ecoles

    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    tresorier = Comptes().create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia", email="julia@test.fr")
    Comptes().ajouter_role(db_session, tresorier, roles.TRESORIER)
    admin = Comptes().create(db_session, ecole_id=ecole.id, role="admin", nom="Roux", prenom="Ana", email="ana@test.fr")
    faux = FauxEnableBanking()
    monkeypatch.setattr(main.core.finances_bank, "client", faux)
    h = entetes_session(tresorier)

    assert client.get("/finances/bank", headers=entetes_session(admin)).status_code == 403
    assert client.get("/finances/bank/banks?q=cic", headers=h).json()["banks"][0]["name"] == "CIC"
    url = client.post("/finances/bank/connect", json={"bank": "CIC", "psuType": "business"}, headers=h).json()["url"]
    state = url.split("state=")[1]
    retour = client.get(f"/finances/bank/return?state={state}&code=code-ok", follow_redirects=False)
    assert retour.status_code == 303 and retour.headers["location"].endswith("/?banque=ok")
    assert client.get("/finances/bank", headers=h).json()["connected"] is True
    # Un retour annulé chez la banque.
    url = client.post("/finances/bank/connect", json={"bank": "CIC"}, headers=h).json()["url"]
    retour = client.get(f"/finances/bank/return?state={url.split('state=')[1]}&error=access_denied", follow_redirects=False)
    assert retour.headers["location"].endswith("/?banque=annule")
    assert client.post("/finances/bank/sync", headers=h).json() == {"added": 0}
