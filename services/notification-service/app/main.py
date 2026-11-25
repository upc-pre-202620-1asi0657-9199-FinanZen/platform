import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header

from .models import HealthResponse, NotificationResponse
from .repository import NotificationRepository


def create_app(database_path: str | None = None) -> FastAPI:
    repository = NotificationRepository(
        database_path
        or os.getenv(
            "FINANZEN_NOTIFICATION_DB_PATH",
            "data/notifications.db",
        )
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        repository.initialize()
        yield

    app = FastAPI(
        title="FinanZen Notification Service",
        version="0.1.0",
        description=(
            "Microservicio responsable de procesar alertas "
            "cuando un presupuesto alcanza su umbral."
        ),
        lifespan=lifespan,
    )

    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["Operations"],
    )
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service="notification-service",
        )

    @app.get(
        "/api/v1/notifications",
        response_model=list[NotificationResponse],
        tags=["Notifications"],
    )
    def list_notifications(
        x_user_id: str = Header(
            min_length=1,
            max_length=80,
            alias="X-User-Id",
        ),
    ) -> list[NotificationResponse]:
        return repository.list_notifications(x_user_id)

    @app.post(
        "/internal/events/budget-threshold-reached",
        tags=["Events"],
    )
    def consume_budget_threshold_reached(event: dict):
        return repository.process_budget_threshold_reached(event)

    return app


app = create_app()