import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, status
from fastapi.responses import JSONResponse

from .models import (
    DeviceConnectionCreate,
    DeviceResponse,
    HealthResponse,
    RawReading,
)
from .normalizer import ReadingNormalizer
from .repository import DeviceIntegrationRepository, DeviceNotFoundError


def create_app(database_path: str | None = None) -> FastAPI:
    repository = DeviceIntegrationRepository(
        database_path
        or os.getenv(
            "FINANZEN_DEVICE_DB_PATH",
            "data/device_integration.db",
        )
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        repository.initialize()
        yield

    app = FastAPI(
        title="FinanZen Device Integration Service",
        version="0.1.0",
        description=(
            "Microservicio responsable de registrar dispositivos, "
            "normalizar lecturas IoT y almacenar telemetría."
        ),
        lifespan=lifespan,
    )

    @app.exception_handler(DeviceNotFoundError)
    async def device_not_found_handler(_, __):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "Device not found or not active"},
        )

    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["Operations"],
    )
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service="device-integration-service",
        )

    @app.post(
        "/api/v1/devices/connections",
        response_model=DeviceResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["Devices"],
    )
    def connect_device(
        device: DeviceConnectionCreate,
        x_user_id: str = Header(
            min_length=1,
            max_length=80,
            alias="X-User-Id",
        ),
    ) -> DeviceResponse:
        return repository.register_device(
            x_user_id,
            device,
        )

    @app.get(
        "/api/v1/devices",
        response_model=list[DeviceResponse],
        tags=["Devices"],
    )
    def list_devices(
        x_user_id: str = Header(
            min_length=1,
            max_length=80,
            alias="X-User-Id",
        ),
    ) -> list[DeviceResponse]:
        return repository.get_devices(x_user_id)

    @app.delete(
        "/api/v1/devices/{device_id}/connection",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["Devices"],
    )
    def disconnect_device(
        device_id: str,
        x_user_id: str = Header(
            min_length=1,
            max_length=80,
            alias="X-User-Id",
        ),
    ):
        repository.revoke_device(
            x_user_id,
            device_id,
        )

    @app.get(
        "/api/v1/devices/{device_id}/sync-status",
        tags=["Devices"],
    )
    def sync_status(
        device_id: str,
        x_user_id: str = Header(
            min_length=1,
            max_length=80,
            alias="X-User-Id",
        ),
    ):
        device = repository.get_device(
            x_user_id,
            device_id,
        )

        return {
            "device_id": device.device_id,
            "status": device.status,
            "sync_enabled": device.status == "active",
        }

    @app.post(
        "/api/v1/readings",
        tags=["Telemetry"],
    )
    def receive_reading(
        reading: RawReading,
        x_user_id: str = Header(
            min_length=1,
            max_length=80,
            alias="X-User-Id",
        ),
    ):
        device = repository.get_device(
            x_user_id,
            reading.device_id,
        )

        normalized = ReadingNormalizer.normalize(
            device.owner_id,
            reading,
        )

        result = repository.save_reading(normalized)

        return {
            **result,
            "normalized_reading": normalized.model_dump(
                mode="json"
            ),
        }

    @app.get(
        "/api/v1/readings",
        tags=["Telemetry"],
    )
    def list_readings(
        x_user_id: str = Header(
            min_length=1,
            max_length=80,
            alias="X-User-Id",
        ),
    ):
        return repository.list_readings(x_user_id)

    return app


app = create_app()