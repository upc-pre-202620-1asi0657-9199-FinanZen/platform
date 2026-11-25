from fastapi.testclient import TestClient

from app.main import create_app


def transaction_payload(amount: str = "100.00", transaction_type: str = "income") -> dict:
    return {
        "account_id": "cash-account",
        "type": transaction_type,
        "amount": amount,
        "currency": "PEN",
        "category": "salary" if transaction_type == "income" else "food",
        "occurred_at": "2026-10-01T10:00:00Z",
        "description": "Functional advance",
    }


def test_create_is_idempotent_and_rejects_key_reuse(tmp_path):
    app = create_app(str(tmp_path / "records.db"))
    headers = {"X-User-Id": "user-1", "Idempotency-Key": "movement-0001"}

    with TestClient(app) as client:
        first = client.post("/api/v1/transactions", json=transaction_payload(), headers=headers)
        replay = client.post("/api/v1/transactions", json=transaction_payload(), headers=headers)
        conflict = client.post(
            "/api/v1/transactions",
            json=transaction_payload(amount="200.00"),
            headers=headers,
        )

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.headers["Idempotent-Replayed"] == "true"
    assert replay.json()["id"] == first.json()["id"]
    assert conflict.status_code == 409


def test_summary_calculates_balance_and_isolates_users(tmp_path):
    app = create_app(str(tmp_path / "records.db"))

    with TestClient(app) as client:
        client.post(
            "/api/v1/transactions",
            json=transaction_payload(amount="1000.00", transaction_type="income"),
            headers={"X-User-Id": "user-1", "Idempotency-Key": "income-0001"},
        )
        client.post(
            "/api/v1/transactions",
            json=transaction_payload(amount="125.50", transaction_type="expense"),
            headers={"X-User-Id": "user-1", "Idempotency-Key": "expense-0001"},
        )
        client.post(
            "/api/v1/transactions",
            json=transaction_payload(amount="9999.00", transaction_type="income"),
            headers={"X-User-Id": "user-2", "Idempotency-Key": "income-0002"},
        )

        summary = client.get(
            "/api/v1/summary?month=2026-10",
            headers={"X-User-Id": "user-1"},
        )
        transactions = client.get(
            "/api/v1/transactions", headers={"X-User-Id": "user-1"}
        )

    assert summary.status_code == 200
    assert summary.json() == {
        "user_id": "user-1",
        "month": "2026-10",
        "currency": "PEN",
        "income": "1000.00",
        "expenses": "125.50",
        "balance": "874.50",
        "transaction_count": 2,
    }
    assert transactions.status_code == 200
    assert len(transactions.json()) == 2
    assert {item["user_id"] for item in transactions.json()} == {"user-1"}


def test_frontend_is_served(tmp_path):
    app = create_app(str(tmp_path / "records.db"))

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "FinanZen" in response.text
    assert "Control financiero" in response.text

