from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from app.models import DeviceConnectionCreate, RawReading
from app.normalizer import ReadingNormalizer
from app.repository import DeviceIntegrationRepository, DeviceNotFoundError


scenarios("features/device_telemetry.feature")


@pytest.fixture
def context(tmp_path):
    database_path = tmp_path / "bdd_device.db"

    repository = DeviceIntegrationRepository(str(database_path))
    repository.initialize()

    return {
        "repository": repository,
        "normalizer": ReadingNormalizer(),
        "user_id": "user-1",
        "device_id": None,
        "result": None,
        "reading": None,
    }


@given(
    parsers.parse(
        'user "{user_id}" has no registered device with id "{device_id}"'
    )
)
def no_registered_device(context, user_id, device_id):
    context["user_id"] = user_id
    context["device_id"] = device_id


@when(
    parsers.parse(
        'the user connects device "{device_id}" using provider "{provider}"'
    )
)
def connect_device(context, device_id, provider):
    device = DeviceConnectionCreate(
        device_id=device_id,
        provider=provider,
        source="smart-meter",
    )

    context["result"] = context["repository"].register_device(
        context["user_id"],
        device,
    )


@then("the device should be registered")
def device_registered(context):
    devices = context["repository"].get_devices(context["user_id"])

    assert len(devices) == 1


@then(parsers.parse('the device status should be "{status}"'))
def device_status(context, status):
    assert context["result"].status == status


@given(
    parsers.parse(
        'user "{user_id}" has an active device "{device_id}"'
    )
)
def active_device(context, user_id, device_id):
    context["user_id"] = user_id
    context["device_id"] = device_id

    device = DeviceConnectionCreate(
        device_id=device_id,
        provider="demo-provider",
        source="smart-meter",
    )

    context["repository"].register_device(
        user_id,
        device,
    )


@when(
    parsers.parse(
        "the device sends an energy consumption reading of {value:d} Wh"
    )
)
def send_energy_reading(context, value):
    raw = RawReading(
        reading_id="reading-001",
        device_id=context["device_id"],
        measurement_type="energy_consumption",
        value=Decimal(value),
        unit="wh",
        occurred_at="2026-11-25T00:00:00Z",
        source="smart-meter",
    )

    normalized = context["normalizer"].normalize(
        context["user_id"],
        raw,
    )

    context["reading"] = normalized
    context["result"] = context["repository"].save_reading(normalized)


@then(parsers.parse("the reading should be normalized to {value:f} kWh"))
def reading_normalized(context, value):
    assert context["reading"].value == Decimal(str(value))
    assert context["reading"].unit == "kwh"


@then(parsers.parse('the validation status should be "{status}"'))
def validation_status(context, status):
    assert context["reading"].validation_status.value == status


@then("the normalized reading should be stored in the telemetry store")
def reading_stored(context):
    readings = context["repository"].list_readings(context["user_id"])

    assert len(readings) == 1


@then('a "ConsumptionReadingNormalized" event should be generated')
def normalized_event_generated(context):
    events = context["repository"].list_pending_events()

    assert any(
        event["event_type"] == "ConsumptionReadingNormalized"
        for event in events
    )


@given(
    parsers.parse(
        'a telemetry reading with source "{source}" and reading id "{reading_id}" has already been processed'
    )
)
def telemetry_already_processed(context, source, reading_id):
    context["user_id"] = "user-1"
    context["device_id"] = "smart-meter-001"

    device = DeviceConnectionCreate(
        device_id=context["device_id"],
        provider="demo-provider",
        source=source,
    )

    context["repository"].register_device(
        context["user_id"],
        device,
    )

    raw = RawReading(
        reading_id=reading_id,
        device_id=context["device_id"],
        measurement_type="energy_consumption",
        value=Decimal("1500"),
        unit="wh",
        occurred_at="2026-11-25T00:00:00Z",
        source=source,
    )

    normalized = context["normalizer"].normalize(
        context["user_id"],
        raw,
    )

    context["reading"] = normalized
    context["repository"].save_reading(normalized)


@when("the same telemetry reading is received again")
def replay_telemetry(context):
    context["result"] = context["repository"].save_reading(
        context["reading"]
    )


@then("the reading should be ignored")
def telemetry_ignored(context):
    assert context["result"]["status"] == "ignored"


@then("no duplicate telemetry record should be stored")
def no_duplicate_record(context):
    readings = context["repository"].list_readings(context["user_id"])

    assert len(readings) == 1


@then('no duplicate "ConsumptionReadingNormalized" event should be generated')
def no_duplicate_event(context):
    events = context["repository"].list_pending_events()

    assert len(events) == 1


@given(
    parsers.parse(
        'user "{user_id}" has revoked device "{device_id}"'
    )
)
def revoked_device(context, user_id, device_id):
    context["user_id"] = user_id
    context["device_id"] = device_id

    device = DeviceConnectionCreate(
        device_id=device_id,
        provider="demo-provider",
        source="smart-meter",
    )

    context["repository"].register_device(
        user_id,
        device,
    )

    context["repository"].revoke_device(
        user_id,
        device_id,
    )


@when("the revoked device sends a telemetry reading")
def revoked_device_sends_reading(context):
    raw = RawReading(
        reading_id="reading-revoked-001",
        device_id=context["device_id"],
        measurement_type="energy_consumption",
        value=Decimal("1000"),
        unit="wh",
        occurred_at="2026-11-25T00:00:00Z",
        source="smart-meter",
    )

    normalized = context["normalizer"].normalize(
        context["user_id"],
        raw,
    )

    try:
        context["repository"].save_reading(normalized)
        context["result"] = "accepted"
    except DeviceNotFoundError:
        context["result"] = "rejected"


@then("the reading should be rejected")
def reading_rejected(context):
    assert context["result"] == "rejected"