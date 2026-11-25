import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from .models import MonthlySummary, TransactionCreate, TransactionResponse, TransactionType


class IdempotencyConflictError(Exception):
    """Raised when a key is reused with a different request body."""


class FinancialRecordsRepository:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path

    def initialize(self) -> None:
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS transactions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    type TEXT NOT NULL CHECK (type IN ('income', 'expense')),
                    amount TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    category TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    description TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE (user_id, idempotency_key)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_transactions_owner_date "
                "ON transactions(user_id, occurred_at)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS outbox_events (
                    id TEXT PRIMARY KEY,
                    aggregate_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    published_at TEXT
                )
                """
            )

    def create_transaction(
        self,
        user_id: str,
        idempotency_key: str,
        transaction: TransactionCreate,
    ) -> tuple[TransactionResponse, bool]:
        request_hash = self._request_hash(transaction)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM transactions WHERE user_id = ? AND idempotency_key = ?",
                (user_id, idempotency_key),
            ).fetchone()
            if existing is not None:
                if existing["request_hash"] != request_hash:
                    raise IdempotencyConflictError
                return self._to_response(existing), True

            transaction_id = str(uuid4())
            created_at = datetime.now(timezone.utc)
            connection.execute(
                """
                INSERT INTO transactions (
                    id, user_id, idempotency_key, request_hash, account_id, type,
                    amount, currency, category, occurred_at, description, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    transaction_id,
                    user_id,
                    idempotency_key,
                    request_hash,
                    transaction.account_id,
                    transaction.type.value,
                    str(transaction.amount),
                    transaction.currency,
                    transaction.category,
                    transaction.occurred_at.isoformat(),
                    transaction.description,
                    created_at.isoformat(),
                ),
            )
            event_id = str(uuid4())
            event_payload = {
                "event_id": event_id,
                "event_type": "TransactionRecorded",
                "transaction_id": transaction_id,
                "user_id": user_id,
                "account_id": transaction.account_id,
                "type": transaction.type.value,
                "amount": str(transaction.amount),
                "currency": transaction.currency,
                "category": transaction.category,
                "occurred_at": transaction.occurred_at.isoformat(),
                "created_at": created_at.isoformat(),
            }
            connection.execute(
                """
                INSERT INTO outbox_events (
                    id,
                    aggregate_id,
                    event_type,
                    payload,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    transaction_id,
                    "TransactionRecorded",
                    json.dumps(event_payload),
                    "pending",
                    created_at.isoformat(),
                ),
            )
            row = connection.execute(
                "SELECT * FROM transactions WHERE id = ?", (transaction_id,)
            ).fetchone()
            return self._to_response(row), False

    def list_transactions(self, user_id: str) -> list[TransactionResponse]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM transactions
                WHERE user_id = ?
                ORDER BY occurred_at DESC, created_at DESC
                """,
                (user_id,),
            ).fetchall()
        return [self._to_response(row) for row in rows]

    def monthly_summary(self, user_id: str, month: str, currency: str) -> MonthlySummary:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM transactions
                WHERE user_id = ? AND currency = ? AND substr(occurred_at, 1, 7) = ?
                """,
                (user_id, currency, month),
            ).fetchall()

        income = sum(
            (Decimal(row["amount"]) for row in rows if row["type"] == TransactionType.INCOME.value),
            Decimal("0"),
        )
        expenses = sum(
            (Decimal(row["amount"]) for row in rows if row["type"] == TransactionType.EXPENSE.value),
            Decimal("0"),
        )
        return MonthlySummary(
            user_id=user_id,
            month=month,
            currency=currency,
            income=income,
            expenses=expenses,
            balance=income - expenses,
            transaction_count=len(rows),
        )

    def list_pending_events(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM outbox_events
                WHERE status = 'pending'
                ORDER BY created_at ASC
                """
            ).fetchall()

        return [
            {
                "id": row["id"],
                "aggregate_id": row["aggregate_id"],
                "event_type": row["event_type"],
                "payload": json.loads(row["payload"]),
                "status": row["status"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def mark_event_as_published(self, event_id: str) -> None:
        published_at = datetime.now(timezone.utc).isoformat()

        with self._connect() as connection:
            connection.execute(
                """
                UPDATE outbox_events
                SET status = 'published',
                    published_at = ?
                WHERE id = ?
                """,
                (
                    published_at,
                    event_id,
                ),
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _request_hash(transaction: TransactionCreate) -> str:
        payload = transaction.model_dump(mode="json")
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _to_response(row: sqlite3.Row) -> TransactionResponse:
        return TransactionResponse(
            id=row["id"],
            user_id=row["user_id"],
            account_id=row["account_id"],
            type=row["type"],
            amount=Decimal(row["amount"]),
            currency=row["currency"],
            category=row["category"],
            occurred_at=datetime.fromisoformat(row["occurred_at"]),
            description=row["description"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

