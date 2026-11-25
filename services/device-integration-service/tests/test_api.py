from fastapi.testclient import TestClient

from app.main import create_app


def test_device_and_reading_flow_is_idempotent(tmp_path):
    app = create_app(str(tmp_path / "devices.db"))

    with TestClient(app) as client:

        device = client.post(
            "/api/v1/devices/connections",
            headers={
                "X-User-Id": "user-1",
            },
            json={
                "device_id": "smart-meter-001",
                "provider": "demo-provider",
                "source": "smart-meter",
            },
        )

        assert device.status_code == 201

        reading = {
            "reading_id": "reading-001",
            "device_id": "smart-meter-001",
            "measurement_type": "energy_consumption",
            "value": "1500",
            "unit": "wh",
            "occurred_at": "2026-11-24T23:30:00Z",
            "source": "smart-meter",
        }

        first = client.post(
            "/api/v1/readings",
            headers={
                "X-User-Id": "user-1",
            },
            json=reading,
        )

        replay = client.post(
            "/api/v1/readings",
            headers={
                "X-User-Id": "user-1",
            },
            json=reading,
        )

        readings = client.get(
            "/api/v1/readings",
            headers={
                "X-User-Id": "user-1",
            },
        )

    assert first.status_code == 200
    assert first.json()["status"] == "processed"

    assert first.json()["normalized_reading"]["value"] == "1.5"
    assert first.json()["normalized_reading"]["unit"] == "kwh"
    assert (
        first.json()["normalized_reading"]["validation_status"]
        == "valid"
    )

    assert replay.status_code == 200
    assert replay.json()["status"] == "ignored"

    assert readings.status_code == 200
    assert len(readings.json()) == 1