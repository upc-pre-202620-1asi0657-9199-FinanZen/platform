import sqlite3
from decimal import Decimal
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
import json

from .models import BudgetCreate, BudgetResponse, BudgetStatus, BudgetUpdate


class BudgetNotFoundError(Exception):
    pass


class BudgetRepository:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path

    def initialize(self) -> None:
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS budgets (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    limit_amount TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    period TEXT NOT NULL,
                    spent_amount TEXT NOT NULL DEFAULT '0'
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    processed_at TEXT NOT NULL
                )
                """
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

    def create_budget(
        self,
        user_id: str,
        budget: BudgetCreate,
    ) -> BudgetResponse:
        budget_id = str(uuid4())

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO budgets (
                    id,
                    user_id,
                    name,
                    category,
                    limit_amount,
                    currency,
                    period,
                    spent_amount
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    budget_id,
                    user_id,
                    budget.name,
                    budget.category,
                    str(budget.limit_amount),
                    budget.currency,
                    budget.period,
                    "0",
                ),
            )

            row = connection.execute(
                "SELECT * FROM budgets WHERE id = ?",
                (budget_id,),
            ).fetchone()

        return self._to_response(row)

    def update_budget(
        self,
        user_id: str,
        budget_id: str,
        update: BudgetUpdate,
    ) -> BudgetResponse:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM budgets
                WHERE id = ? AND user_id = ?
                """,
                (budget_id, user_id),
            ).fetchone()

            if row is None:
                raise BudgetNotFoundError

            current = dict(row)
            changes = update.model_dump(exclude_none=True)

            for key, value in changes.items():
                current[key] = str(value) if isinstance(value, Decimal) else value

            connection.execute(
                """
                UPDATE budgets
                SET name = ?,
                    category = ?,
                    limit_amount = ?,
                    currency = ?,
                    period = ?
                WHERE id = ? AND user_id = ?
                """,
                (
                    current["name"],
                    current["category"],
                    current["limit_amount"],
                    current["currency"],
                    current["period"],
                    budget_id,
                    user_id,
                ),
            )

            updated = connection.execute(
                """
                SELECT * FROM budgets
                WHERE id = ? AND user_id = ?
                """,
                (budget_id, user_id),
            ).fetchone()

        return self._to_response(updated)

    def get_budget_status(
        self,
        user_id: str,
        budget_id: str,
    ) -> BudgetStatus:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM budgets
                WHERE id = ? AND user_id = ?
                """,
                (budget_id, user_id),
            ).fetchone()

        if row is None:
            raise BudgetNotFoundError

        limit_amount = Decimal(row["limit_amount"])
        spent_amount = Decimal(row["spent_amount"])

        remaining = limit_amount - spent_amount

        usage = (
            (spent_amount / limit_amount) * Decimal("100")
            if limit_amount > 0
            else Decimal("0")
        )

        return BudgetStatus(
            budget_id=row["id"],
            user_id=row["user_id"],
            limit_amount=limit_amount,
            spent_amount=spent_amount,
            remaining_amount=remaining,
            usage_percentage=usage.quantize(Decimal("0.01")),
            threshold_reached=usage >= Decimal("80"),
        )

    def list_budgets(
        self,
        user_id: str,
    ) -> list[BudgetResponse]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM budgets
                WHERE user_id = ?
                ORDER BY name ASC
                """,
                (user_id,),
            ).fetchall()

        return [self._to_response(row) for row in rows]

    def process_transaction_recorded(self, event: dict) -> dict:
        event_id = event["event_id"]

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")

            already_processed = connection.execute(
                """
                SELECT event_id
                FROM processed_events
                WHERE event_id = ?
                """,
                (event_id,),
            ).fetchone()

            if already_processed is not None:
                return {
                    "status": "ignored",
                    "reason": "event_already_processed",
                    "event_id": event_id,
                }

            if event["type"] == "expense":
                rows = connection.execute(
                    """
                    SELECT *
                    FROM budgets
                    WHERE user_id = ?
                    AND category = ?
                    AND currency = ?
                    """,
                    (
                        event["user_id"],
                        event["category"],
                        event["currency"],
                    ),
                ).fetchall()

                for row in rows:
                    current_spent = Decimal(row["spent_amount"])
                    new_spent = current_spent + Decimal(event["amount"])

                    connection.execute(
                        """
                        UPDATE budgets
                        SET spent_amount = ?
                        WHERE id = ?
                        """,
                        (
                            str(new_spent),
                            row["id"],
                        ),
                    )

                    limit_amount = Decimal(row["limit_amount"])

                    usage = (
                        (new_spent / limit_amount) * Decimal("100")
                        if limit_amount > 0
                        else Decimal("0")
                    )

                    if usage >= Decimal("80"):
                        alert_event_id = str(uuid4())
                        created_at = datetime.now(timezone.utc)

                        alert_payload = {
                            "event_id": alert_event_id,
                            "event_type": "BudgetThresholdReached",
                            "budget_id": row["id"],
                            "user_id": row["user_id"],
                            "category": row["category"],
                            "currency": row["currency"],
                            "limit_amount": str(limit_amount),
                            "spent_amount": str(new_spent),
                            "usage_percentage": str(
                                usage.quantize(Decimal("0.01"))
                            ),
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
                                alert_event_id,
                                row["id"],
                                "BudgetThresholdReached",
                                json.dumps(alert_payload),
                                "pending",
                                created_at.isoformat(),
                            ),
                        )

            connection.execute(
                """
                INSERT INTO processed_events (
                    event_id,
                    event_type,
                    processed_at
                )
                VALUES (?, ?, ?)
                """,
                (
                    event_id,
                    event["event_type"],
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

        return {
            "status": "processed",
            "event_id": event_id,
        }

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
    def _to_response(row: sqlite3.Row) -> BudgetResponse:
        limit_amount = Decimal(row["limit_amount"])
        spent_amount = Decimal(row["spent_amount"])
        remaining = limit_amount - spent_amount

        usage = (
            (spent_amount / limit_amount) * Decimal("100")
            if limit_amount > 0
            else Decimal("0")
        )

        return BudgetResponse(
            id=row["id"],
            user_id=row["user_id"],
            name=row["name"],
            category=row["category"],
            limit_amount=limit_amount,
            currency=row["currency"],
            period=row["period"],
            spent_amount=spent_amount,
            remaining_amount=remaining,
            usage_percentage=usage.quantize(Decimal("0.01")),
        )