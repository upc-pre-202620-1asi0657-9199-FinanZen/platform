import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import json
from uuid import uuid4

from .models import (
    DeviceConnectionCreate,
    DeviceResponse,
    NormalizedReading,
)


class DeviceNotFoundError(Exception):
    pass


class DuplicateReadingError(Exception):
    pass


class DeviceIntegrationRepository:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path

    def initialize(self) -> None:
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS devices (
                    device_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    connected_at TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS telemetry (
                    reading_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    device_id TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    measurement_type TEXT NOT NULL,
                    value TEXT NOT NULL,
                    unit TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    validation_status TEXT NOT NULL,
                    PRIMARY KEY (source, reading_id)
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

    def register_device(
        self,
        owner_id: str,
        device: DeviceConnectionCreate,
    ) -> DeviceResponse:
        connected_at = datetime.now(timezone.utc)

        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO devices (
                    device_id,
                    owner_id,
                    provider,
                    source,
                    status,
                    connected_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    device.device_id,
                    owner_id,
                    device.provider,
                    device.source,
                    "active",
                    connected_at.isoformat(),
                ),
            )

            row = connection.execute(
                """
                SELECT *
                FROM devices
                WHERE device_id = ?
                """,
                (device.device_id,),
            ).fetchone()

        return self._to_device_response(row)

    def get_devices(
        self,
        owner_id: str,
    ) -> list[DeviceResponse]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM devices
                WHERE owner_id = ?
                ORDER BY connected_at DESC
                """,
                (owner_id,),
            ).fetchall()

        return [self._to_device_response(row) for row in rows]

    def get_device(
        self,
        owner_id: str,
        device_id: str,
    ) -> DeviceResponse:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM devices
                WHERE owner_id = ?
                  AND device_id = ?
                """,
                (
                    owner_id,
                    device_id,
                ),
            ).fetchone()

        if row is None:
            raise DeviceNotFoundError

        return self._to_device_response(row)

    def revoke_device(
        self,
        owner_id: str,
        device_id: str,
    ) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE devices
                SET status = 'revoked'
                WHERE owner_id = ?
                  AND device_id = ?
                """,
                (
                    owner_id,
                    device_id,
                ),
            )

        if cursor.rowcount == 0:
            raise DeviceNotFoundError

    def save_reading(
        self,
        reading: NormalizedReading,
    ) -> dict:
        with self._connect() as connection:
            device = connection.execute(
                """
                SELECT *
                FROM devices
                WHERE device_id = ?
                  AND owner_id = ?
                """,
                (
                    reading.device_id,
                    reading.owner_id,
                ),
            ).fetchone()

            if device is None:
                raise DeviceNotFoundError

            if device["status"] != "active":
                raise DeviceNotFoundError

            existing = connection.execute(
                """
                SELECT reading_id
                FROM telemetry
                WHERE source = ?
                  AND reading_id = ?
                """,
                (
                    reading.source,
                    reading.reading_id,
                ),
            ).fetchone()

            if existing is not None:
                return {
                    "status": "ignored",
                    "reason": "reading_already_processed",
                    "reading_id": reading.reading_id,
                }

            connection.execute(
                """
                INSERT INTO telemetry (
                    reading_id,
                    source,
                    device_id,
                    owner_id,
                    measurement_type,
                    value,
                    unit,
                    occurred_at,
                    received_at,
                    validation_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    reading.reading_id,
                    reading.source,
                    reading.device_id,
                    reading.owner_id,
                    reading.measurement_type,
                    str(reading.value),
                    reading.unit,
                    reading.occurred_at.isoformat(),
                    reading.received_at.isoformat(),
                    reading.validation_status.value,
                ),
            )

            if reading.validation_status.value == "valid":
                event_id = str(uuid4())

                payload = {
                    "event_id": event_id,
                    "event_type": "ConsumptionReadingNormalized",
                    "reading_id": reading.reading_id,
                    "device_id": reading.device_id,
                    "owner_id": reading.owner_id,
                    "measurement_type": reading.measurement_type,
                    "value": str(reading.value),
                    "unit": reading.unit,
                    "occurred_at": reading.occurred_at.isoformat(),
                    "received_at": reading.received_at.isoformat(),
                    "source": reading.source,
                    "validation_status": reading.validation_status.value,
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
                        reading.reading_id,
                        "ConsumptionReadingNormalized",
                        json.dumps(payload),
                        "pending",
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )

        return {
            "status": "processed",
            "reading_id": reading.reading_id,
        }

    def list_readings(
        self,
        owner_id: str,
    ) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM telemetry
                WHERE owner_id = ?
                ORDER BY occurred_at DESC
                """,
                (owner_id,),
            ).fetchall()

        return [
            {
                "reading_id": row["reading_id"],
                "source": row["source"],
                "device_id": row["device_id"],
                "owner_id": row["owner_id"],
                "measurement_type": row["measurement_type"],
                "value": Decimal(row["value"]),
                "unit": row["unit"],
                "occurred_at": row["occurred_at"],
                "received_at": row["received_at"],
                "validation_status": row["validation_status"],
            }
            for row in rows
        ]

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
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE outbox_events
                SET status = 'published',
                    published_at = ?
                WHERE id = ?
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    event_id,
                ),
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _to_device_response(row: sqlite3.Row) -> DeviceResponse:
        return DeviceResponse(
            device_id=row["device_id"],
            owner_id=row["owner_id"],
            provider=row["provider"],
            source=row["source"],
            status=row["status"],
            connected_at=datetime.fromisoformat(row["connected_at"]),
        )