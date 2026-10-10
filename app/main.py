import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, Query, Response, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .models import HealthResponse, MonthlySummary, TransactionCreate, TransactionResponse
from .repository import FinancialRecordsRepository, IdempotencyConflictError

MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def create_app(database_path: str | None = None) -> FastAPI:
    repository = FinancialRecordsRepository(
        database_path or os.getenv("FINANZEN_DB_PATH", "data/financial_records.db")
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        repository.initialize()
        yield

    app = FastAPI(
        title="FinanZen Financial Records Service",
        version="0.1.0",
        description=(
            "Avance funcional de US01, US10, US11 y US12: registra movimientos "
            "idempotentes y consulta un resumen mensual aislado por usuario."
        ),
        lifespan=lifespan,
    )

    @app.exception_handler(IdempotencyConflictError)
    async def idempotency_conflict_handler(_, __):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": "The Idempotency-Key was already used with a different request body."
            },
        )

    @app.get("/health", response_model=HealthResponse, tags=["Operations"])
    def health() -> HealthResponse:
        return HealthResponse(status="ok", service="financial-records-service")

    @app.post(
        "/api/v1/transactions",
        response_model=TransactionResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["Transactions"],
    )
    def create_transaction(
        transaction: TransactionCreate,
        response: Response,
        x_user_id: str = Header(min_length=1, max_length=80, alias="X-User-Id"),
        idempotency_key: str = Header(min_length=8, max_length=120, alias="Idempotency-Key"),
    ) -> TransactionResponse:
        created, replayed = repository.create_transaction(
            x_user_id, idempotency_key, transaction
        )
        response.headers["Idempotent-Replayed"] = str(replayed).lower()
        if replayed:
            response.status_code = status.HTTP_200_OK
        return created

    @app.get(
        "/api/v1/transactions",
        response_model=list[TransactionResponse],
        tags=["Transactions"],
    )
    def list_transactions(
        x_user_id: str = Header(min_length=1, max_length=80, alias="X-User-Id"),
    ) -> list[TransactionResponse]:
        return repository.list_transactions(x_user_id)

    @app.get(
        "/api/v1/summary",
        response_model=MonthlySummary,
        tags=["Reports"],
    )
    def monthly_summary(
        response: Response,
        month: str = Query(description="Month in YYYY-MM format", examples=["2026-10"]),
        currency: str = Query(default="PEN", pattern=r"^[A-Z]{3}$"),
        x_user_id: str = Header(min_length=1, max_length=80, alias="X-User-Id"),
    ) -> MonthlySummary:
        if not MONTH_PATTERN.fullmatch(month):
            response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={"detail": "month must use the YYYY-MM format"},
            )
        return repository.monthly_summary(x_user_id, month, currency)

    frontend_path = Path(__file__).resolve().parent.parent / "frontend"
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

    return app


app = create_app()

