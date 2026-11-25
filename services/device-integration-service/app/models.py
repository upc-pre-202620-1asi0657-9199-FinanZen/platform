from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ValidationStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"


class DeviceConnectionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    device_id: str = Field(min_length=1, max_length=80)
    provider: str = Field(min_length=1, max_length=80)
    source: str = Field(min_length=1, max_length=80)


class DeviceResponse(BaseModel):
    device_id: str
    owner_id: str
    provider: str
    source: str
    status: str
    connected_at: datetime


class RawReading(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    reading_id: str = Field(min_length=1, max_length=120)
    device_id: str = Field(min_length=1, max_length=80)
    measurement_type: str = Field(min_length=1, max_length=80)
    value: Decimal
    unit: str = Field(min_length=1, max_length=20)
    occurred_at: datetime
    source: str = Field(min_length=1, max_length=80)


class NormalizedReading(BaseModel):
    reading_id: str
    device_id: str
    owner_id: str
    measurement_type: str
    value: Decimal
    unit: str
    occurred_at: datetime
    received_at: datetime
    source: str
    validation_status: ValidationStatus


class HealthResponse(BaseModel):
    status: str
    service: str