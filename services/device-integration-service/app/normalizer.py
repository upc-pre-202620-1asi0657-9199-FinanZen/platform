from datetime import datetime, timezone
from decimal import Decimal

from .models import NormalizedReading, RawReading, ValidationStatus


class ReadingNormalizer:

    @staticmethod
    def normalize(
        owner_id: str,
        reading: RawReading,
    ) -> NormalizedReading:

        value = reading.value
        unit = reading.unit.lower()

        validation_status = ValidationStatus.VALID

        if reading.measurement_type == "energy_consumption":

            if unit == "wh":
                value = value / Decimal("1000")
                unit = "kwh"

            elif unit != "kwh":
                validation_status = ValidationStatus.INVALID

            if value < 0:
                validation_status = ValidationStatus.INVALID

        elif reading.measurement_type == "fuel_consumption":

            if unit not in {"l", "liter", "liters"}:
                validation_status = ValidationStatus.INVALID
            else:
                unit = "l"

            if value < 0:
                validation_status = ValidationStatus.INVALID

        return NormalizedReading(
            reading_id=reading.reading_id,
            device_id=reading.device_id,
            owner_id=owner_id,
            measurement_type=reading.measurement_type,
            value=value,
            unit=unit,
            occurred_at=reading.occurred_at,
            received_at=datetime.now(timezone.utc),
            source=reading.source,
            validation_status=validation_status,
        )