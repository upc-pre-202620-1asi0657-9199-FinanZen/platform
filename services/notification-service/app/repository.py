import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from .models import NotificationResponse


class NotificationRepository:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path

    def initialize(self) -> None:
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS notifications (
                    id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL UNIQUE,
                    user_id TEXT NOT NULL,
                    budget_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    limit_amount TEXT NOT NULL,
                    spent_amount TEXT NOT NULL,
                    usage_percentage TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def process_budget_threshold_reached(self, event: dict) -> dict:
        with self._connect() as connection:
            existing = connection.execute(
                """
                SELECT *
                FROM notifications
                WHERE event_id = ?
                """,
                (event["event_id"],),
            ).fetchone()

            if existing is not None:
                return {
                    "status": "ignored",
                    "reason": "event_already_processed",
                    "event_id": event["event_id"],
                }

            notification_id = str(uuid4())
            created_at = datetime.now(timezone.utc)

            connection.execute(
                """
                INSERT INTO notifications (
                    id,
                    event_id,
                    user_id,
                    budget_id,
                    category,
                    currency,
                    limit_amount,
                    spent_amount,
                    usage_percentage,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    notification_id,
                    event["event_id"],
                    event["user_id"],
                    event["budget_id"],
                    event["category"],
                    event["currency"],
                    event["limit_amount"],
                    event["spent_amount"],
                    event["usage_percentage"],
                    "delivered",
                    created_at.isoformat(),
                ),
            )

        return {
            "status": "processed",
            "event_id": event["event_id"],
            "notification_id": notification_id,
        }

    def list_notifications(self, user_id: str) -> list[NotificationResponse]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM notifications
                WHERE user_id = ?
                ORDER BY created_at DESC
                """,
                (user_id,),
            ).fetchall()

        return [self._to_response(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _to_response(row: sqlite3.Row) -> NotificationResponse:
        return NotificationResponse(
            id=row["id"],
            event_id=row["event_id"],
            user_id=row["user_id"],
            budget_id=row["budget_id"],
            category=row["category"],
            currency=row["currency"],
            limit_amount=Decimal(row["limit_amount"]),
            spent_amount=Decimal(row["spent_amount"]),
            usage_percentage=Decimal(row["usage_percentage"]),
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )