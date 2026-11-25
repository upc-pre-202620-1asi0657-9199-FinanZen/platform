from fastapi.testclient import TestClient

from app.main import create_app


def budget_payload() -> dict:
    return {
        "name": "Monthly food budget",
        "category": "food",
        "limit_amount": "500.00",
        "currency": "PEN",
        "period": "monthly",
    }


def test_create_budget(tmp_path):
    app = create_app(str(tmp_path / "budgets.db"))

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/budgets",
            json=budget_payload(),
            headers={"X-User-Id": "user-1"},
        )

    assert response.status_code == 201
    assert response.json()["user_id"] == "user-1"
    assert response.json()["limit_amount"] == "500.00"
    assert response.json()["spent_amount"] == "0"


def test_update_and_status(tmp_path):
    app = create_app(str(tmp_path / "budgets.db"))

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/budgets",
            json=budget_payload(),
            headers={"X-User-Id": "user-1"},
        )

        budget_id = created.json()["id"]

        updated = client.put(
            f"/api/v1/budgets/{budget_id}",
            json={"limit_amount": "750.00"},
            headers={"X-User-Id": "user-1"},
        )

        status_response = client.get(
            f"/api/v1/budgets/{budget_id}/status",
            headers={"X-User-Id": "user-1"},
        )

    assert updated.status_code == 200
    assert updated.json()["limit_amount"] == "750.00"

    assert status_response.status_code == 200
    assert status_response.json()["threshold_reached"] is False


def test_reports_are_isolated_by_user(tmp_path):
    app = create_app(str(tmp_path / "budgets.db"))

    with TestClient(app) as client:
        client.post(
            "/api/v1/budgets",
            json=budget_payload(),
            headers={"X-User-Id": "user-1"},
        )

        client.post(
            "/api/v1/budgets",
            json={
                "name": "Entertainment",
                "category": "entertainment",
                "limit_amount": "300.00",
                "currency": "PEN",
                "period": "monthly",
            },
            headers={"X-User-Id": "user-2"},
        )

        response = client.get(
            "/api/v1/reports",
            headers={"X-User-Id": "user-1"},
        )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["user_id"] == "user-1"