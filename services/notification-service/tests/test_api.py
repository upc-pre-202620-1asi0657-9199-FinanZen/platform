from fastapi.testclient import TestClient

from app.main import create_app


def test_notification_is_created_and_is_idempotent(tmp_path):
    app = create_app(str(tmp_path / "notifications.db"))

    event = {
        "event_id": "alert-001",
        "event_type": "BudgetThresholdReached",
        "budget_id": "budget-001",
        "user_id": "user-1",
        "category": "food",
        "currency": "PEN",
        "limit_amount": "500.00",
        "spent_amount": "400.00",
        "usage_percentage": "80.00",
        "created_at": "2026-11-24T23:00:00Z",
    }

    with TestClient(app) as client:
        first = client.post(
            "/internal/events/budget-threshold-reached",
            json=event,
        )

        replay = client.post(
            "/internal/events/budget-threshold-reached",
            json=event,
        )

        notifications = client.get(
            "/api/v1/notifications",
            headers={"X-User-Id": "user-1"},
        )

    assert first.status_code == 200
    assert first.json()["status"] == "processed"

    assert replay.status_code == 200
    assert replay.json()["status"] == "ignored"

    assert notifications.status_code == 200
    assert len(notifications.json()) == 1
    assert notifications.json()[0]["usage_percentage"] == "80.00"