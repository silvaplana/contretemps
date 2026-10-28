"""Connexion bancaire d'une organisation (spec/modules/financier.md §3.5),
par Enable Banking (enablebanking.py). Repris de Sambo Admin
(`test-python`, bankaccounts/bankaccounts.py et bankstatements.sync_live),
pour plusieurs organisations :

- la banque se choisit par organisation, au moment de connecter ;
- la connexion (session chiffrée, comptes autorisés, expiration) est en
  base, une ligne par organisation (`FinBankConnection`) ;
- le retour de la banque arrive sur une seule adresse ; `state` dit quelle
  organisation revient ;
- un compte que la banque montre et qui n'a encore aucun relevé est créé
  depuis son IBAN ; son solde lu à la banque sert de point de départ.

Les opérations lues à la banque sont provisoires (`source = banque`) : seules
celles d'après le dernier relevé du compte sont gardées, elles sont
remplacées à chaque lecture (lire deux fois n'ajoute rien), et le relevé
qui les couvre les efface en arrivant (service.py) : le relevé fait foi.
"""

from __future__ import annotations

import secrets
import time
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .enablebanking import EnableBankingClient, EnableBankingError
from .models import SOURCE_BANK, FinAccount, FinBankConnection, FinOperation, FinStatement
from .ports import Member
from .service import Finances

# Le temps de passer par sa banque.
STATE_TTL = timedelta(minutes=30)
# Profondeur d'historique : 90 jours, le maximum que les banques acceptent en
# lecture ordinaire (constaté dans Sambo Admin).
HISTORY_DAYS = 90
# Types de solde (ISO 20022) par ordre de préférence : comptable de clôture,
# provisoire, disponible.
BALANCE_TYPES = ("CLBD", "ITBD", "XPCD", "CLAV", "ITAV")
# Liste des banques : relue au plus une fois par jour.
BANKS_TTL_SECONDS = 24 * 3600


class BankError(RuntimeError):
    """Message lisible, montré tel quel."""


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _check(member: Member) -> None:
    if not member.keeps_accounts:
        raise PermissionError("Réservé aux trésoriers")


def _mask(iban: str) -> str:
    return f"•••• {iban[-4:]}" if len(iban) >= 4 else "••••"


def _suffix(iban: str) -> str:
    """Les 3 derniers chiffres du numéro de compte (avant la clé RIB) :
    ce qui distingue deux comptes d'une même agence (« 401 », « 403 »)."""
    return iban[-5:-2] if len(iban) >= 5 else iban


def _kind_and_name(account: dict) -> tuple[str, str]:
    """(nature, nom par défaut) d'un compte vu par la banque."""
    product = (account.get("product") or account.get("name") or "").strip()
    savings = account.get("cash_account_type") == "SVGS" or "LIVRET" in product.upper()
    base = (product[:1].upper() + product[1:]) if product else ("Livret" if savings else "Compte courant")
    return ("savings" if savings else "checking"), f"{base} {_suffix(account['iban'])}".strip()


class Bank:
    def __init__(
        self,
        client: EnableBankingClient | None,
        finances: Finances,
        encrypt: Callable[[str], str],
        decrypt: Callable[[str], str | None],
    ) -> None:
        """client : None si la connexion bancaire n'est pas configurée sur le
        serveur (pas de clé) ; encrypt/decrypt : chiffrement de la session,
        fourni par l'appli hôte."""
        self.client = client
        self.finances = finances
        self.encrypt = encrypt
        self.decrypt = decrypt
        self._banks: tuple[float, list[dict]] | None = None

    # ----- lecture -----

    def _connection(self, db: Session, org_id: int) -> FinBankConnection | None:
        return db.scalar(select(FinBankConnection).where(FinBankConnection.org_id == org_id))

    @staticmethod
    def _active(connection: FinBankConnection | None) -> bool:
        return bool(
            connection is not None
            and connection.session_encrypted
            and connection.valid_until is not None
            and connection.valid_until > _now()
        )

    def status(self, db: Session, member: Member) -> dict:
        """Ce que montre l'écran : configurée sur le serveur ou non, banque,
        connexion active jusqu'à quand, comptes autorisés et suivis."""
        _check(member)
        connection = self._connection(db, member.org_id)
        if connection is None or not connection.session_encrypted:
            return {"configured": self.client is not None, "connected": False, "bank": None, "accounts": []}
        comptes = {
            a.bank_uid: a
            for a in db.scalars(select(FinAccount).where(FinAccount.org_id == member.org_id, FinAccount.bank_uid.is_not(None)))
        }
        return {
            "configured": self.client is not None,
            "connected": self._active(connection),
            "bank": connection.bank,
            "psuType": connection.psu_type,
            "validUntil": connection.valid_until.date().isoformat() if connection.valid_until else None,
            "lastSyncAt": connection.last_sync_at.isoformat() + "Z" if connection.last_sync_at else None,
            "lastError": connection.last_error,
            "accounts": [
                {
                    "uid": a["uid"],
                    "iban": _mask(a["iban"]),
                    "name": comptes[a["uid"]].name if a["uid"] in comptes else _kind_and_name(a)[1],
                    "followed": bool(a.get("followed")),
                }
                for a in connection.accounts
            ],
        }

    def banks(self, member: Member, query: str = "", country: str = "FR") -> list[dict]:
        """Les banques du pays dont le nom contient `query`."""
        _check(member)
        if self.client is None:
            raise BankError("La connexion bancaire n'est pas configurée sur le serveur.")
        if self._banks is None or time.time() - self._banks[0] > BANKS_TTL_SECONDS:
            try:
                self._banks = (time.time(), self.client.list_banks(country))
            except EnableBankingError as exc:
                raise BankError(str(exc)) from exc
        texte = query.strip().lower()
        return [b for b in self._banks[1] if texte in b["name"].lower()][:50]

    # ----- connexion -----

    def connect(self, db: Session, member: Member, bank: str, psu_type: str = "personal", country: str = "FR") -> str:
        """Démarre la connexion : retourne l'adresse de la banque où envoyer
        la personne. La connexion précédente reste valable tant que la
        nouvelle n'a pas abouti."""
        _check(member)
        if self.client is None:
            raise BankError("La connexion bancaire n'est pas configurée sur le serveur.")
        if psu_type not in ("personal", "business"):
            raise BankError("Espace inconnu : particuliers ou professionnels.")
        state = secrets.token_urlsafe(24)
        try:
            url = self.client.start_authorization(state, bank, country, psu_type)
        except EnableBankingError as exc:
            raise BankError(str(exc)) from exc
        connection = self._connection(db, member.org_id)
        if connection is None:
            connection = FinBankConnection(org_id=member.org_id, bank=bank, country=country, psu_type=psu_type, accounts=[])
            db.add(connection)
        # La banque et l'espace demandés, appliqués au retour.
        connection.state, connection.state_at = state, _now()
        connection.pending = {"bank": bank, "psu_type": psu_type, "country": country}
        db.commit()
        return url

    def complete(self, db: Session, code: str, state: str) -> int:
        """Au retour de la banque : vérifie `state`, échange le code contre
        une session, garde les comptes autorisés, puis lit la banque une
        première fois. Retourne l'organisation qui revient."""
        connection = db.scalar(select(FinBankConnection).where(FinBankConnection.state == state)) if state else None
        if connection is None or connection.state_at is None or _now() - connection.state_at > STATE_TTL:
            raise BankError("Retour de la banque inattendu ou expiré : recommencez la connexion.")
        if self.client is None:
            raise BankError("La connexion bancaire n'est pas configurée sur le serveur.")
        demande = connection.pending or {}
        connection.state, connection.state_at, connection.pending = None, None, None
        try:
            data = self.client.create_session(code)
        except EnableBankingError as exc:
            connection.last_error = str(exc)
            db.commit()
            raise BankError(str(exc)) from exc
        if demande:
            connection.bank, connection.psu_type, connection.country = demande["bank"], demande["psu_type"], demande["country"]
        anciens = {a["uid"]: a.get("followed", True) for a in connection.accounts}
        connection.session_encrypted = self.encrypt(data["session_id"])
        connection.valid_until = datetime.fromisoformat(data["access"]["valid_until"].replace("Z", "+00:00")).astimezone(UTC).replace(tzinfo=None)
        connection.accounts = [
            {
                "uid": a["uid"],
                "iban": ((a.get("account_id") or {}).get("iban") or "").replace(" ", ""),
                "name": a.get("name") or "",
                "product": a.get("product") or a.get("details") or "",
                "cash_account_type": a.get("cash_account_type") or "",
                # Tous suivis au départ (une carte, sans IBAN, jamais).
                "followed": anciens.get(a["uid"], True),
            }
            for a in data.get("accounts", [])
            if a.get("uid") and (a.get("account_id") or {}).get("iban")
        ]
        connection.connected_at, connection.last_error = _now(), None
        db.commit()
        try:
            self._sync(db, connection)
        except BankError:
            pass  # noté dans last_error ; la connexion, elle, est faite
        return connection.org_id

    def follow(self, db: Session, member: Member, uids: list[str]) -> dict:
        """Choisit les comptes suivis parmi ceux que la banque a autorisés."""
        _check(member)
        connection = self._connection(db, member.org_id)
        if connection is None:
            raise BankError("Aucune banque connectée.")
        voulus = set(uids)
        connection.accounts = [{**a, "followed": a["uid"] in voulus} for a in connection.accounts]
        db.commit()
        return self.status(db, member)

    # ----- lecture des comptes -----

    def sync(self, db: Session, member: Member) -> dict:
        """« Actualiser » : relit soldes et opérations des comptes suivis."""
        _check(member)
        connection = self._connection(db, member.org_id)
        if not self._active(connection):
            raise BankError("Banque non connectée, ou connexion expirée : reconnectez la banque.")
        return self._sync(db, connection)

    def sync_all(self, db: Session) -> int:
        """Lecture automatique de toutes les organisations connectées ;
        retourne le nombre d'opérations nouvelles."""
        total = 0
        for connection in list(db.scalars(select(FinBankConnection))):
            if self._active(connection):
                try:
                    total += self._sync(db, connection)["added"]
                except BankError:
                    continue
        return total

    @staticmethod
    def _pick_balance(balances: list[dict]) -> float | None:
        by_type = {b.get("balance_type"): b for b in balances}
        for balance_type in BALANCE_TYPES:
            if balance_type in by_type:
                return float(by_type[balance_type]["balance_amount"]["amount"])
        return float(balances[0]["balance_amount"]["amount"]) if balances else None

    @staticmethod
    def _to_operation(transaction: dict) -> dict:
        amount = float(transaction["transaction_amount"]["amount"])
        debit = transaction.get("credit_debit_indicator") == "DBIT"
        counterparty = transaction.get("creditor" if debit else "debtor") or {}
        label = " ".join(transaction.get("remittance_information") or []).strip() or counterparty.get("name") or "—"
        day = transaction.get("booking_date") or transaction.get("value_date") or transaction.get("transaction_date") or ""
        return {
            "date": day,
            "value_date": transaction.get("value_date") or day,
            "label": label[:255],
            "amount": round((-abs(amount) if debit else abs(amount)) * 100),
        }

    def _account_for(self, db: Session, org_id: int, bank_account: dict) -> FinAccount:
        """Le compte de l'organisation qui correspond : déjà relié, ou dont le
        numéro (lu sur un relevé) est dans l'IBAN, sinon créé depuis l'IBAN."""
        iban = bank_account["iban"]
        comptes = list(db.scalars(select(FinAccount).where(FinAccount.org_id == org_id)))
        account = next((a for a in comptes if a.bank_uid == bank_account["uid"]), None)
        account = account or next((a for a in comptes if a.number == iban or (a.number and a.number in iban)), None)
        if account is None:
            kind, name = _kind_and_name(bank_account)
            account = FinAccount(org_id=org_id, number=iban, name=name, kind=kind)
            db.add(account)
        account.bank_uid = bank_account["uid"]
        db.flush()
        return account

    def _sync(self, db: Session, connection: FinBankConnection) -> dict:
        added = 0
        try:
            for bank_account in [a for a in connection.accounts if a.get("followed")]:
                balance = self._pick_balance(self.client.get_balances(bank_account["uid"]))
                raw: list[dict] = []
                continuation_key = None
                date_from = (date.today() - timedelta(days=HISTORY_DAYS)).isoformat()
                for _ in range(10):
                    page = self.client.get_transactions(bank_account["uid"], date_from, continuation_key)
                    raw.extend(page.get("transactions", []))
                    continuation_key = page.get("continuation_key")
                    if not continuation_key:
                        break
                account = self._account_for(db, connection.org_id, bank_account)
                if balance is not None:
                    account.bank_balance, account.bank_balance_date = round(balance * 100), date.today()
                added += self._store_provisional(db, account, [self._to_operation(t) for t in raw])
        except EnableBankingError as exc:
            db.rollback()
            connection.last_error = str(exc)
            db.commit()
            raise BankError(str(exc)) from exc
        self.finances._link_transfers(db, connection.org_id)
        connection.last_sync_at, connection.last_error = _now(), None
        db.commit()
        return {"added": added}

    @staticmethod
    def _store_provisional(db: Session, account: FinAccount, operations: list[dict]) -> int:
        """Remplace les opérations provisoires du compte d'après son dernier
        relevé par celles lues à la banque ; retourne le nombre de nouvelles."""
        last_end = db.scalar(select(func.max(FinStatement.end_date)).where(FinStatement.account_id == account.id))
        fetched = sorted(
            (op for op in operations if op["date"] and (last_end is None or date.fromisoformat(op["date"]) > last_end)),
            key=lambda op: op["date"],
        )
        if not fetched:
            return 0
        since = date.fromisoformat(fetched[0]["date"])
        anciennes = list(
            db.scalars(
                select(FinOperation).where(
                    FinOperation.account_id == account.id, FinOperation.source == SOURCE_BANK, FinOperation.date >= since
                )
            )
        )
        connues = [(o.date.isoformat(), o.label, o.amount) for o in anciennes]
        delete_provisional(db, anciennes)
        added = 0
        for position, op in enumerate(fetched):
            db.add(
                FinOperation(
                    account_id=account.id,
                    statement_id=None,
                    source=SOURCE_BANK,
                    position=position,
                    date=date.fromisoformat(op["date"]),
                    value_date=date.fromisoformat(op["value_date"]),
                    label=op["label"],
                    details="",
                    amount=op["amount"],
                )
            )
            key = (op["date"], op["label"], op["amount"])
            if key in connues:
                connues.remove(key)
            else:
                added += 1
        db.flush()
        return added


def delete_provisional(db: Session, operations: list[FinOperation]) -> None:
    """Efface des opérations provisoires ; la jumelle d'un virement interne
    n'est plus reliée (elle le sera de nouveau si besoin)."""
    ids = {o.id for o in operations}
    if not ids:
        return
    for twin in db.scalars(select(FinOperation).where(FinOperation.transfer_id.in_(ids))):
        twin.transfer_id = None
    for op in operations:
        db.delete(op)
    db.flush()
