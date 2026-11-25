import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, status
from fastapi.responses import JSONResponse

from .models import (
    BudgetCreate,
    BudgetResponse,
    BudgetStatus,
    BudgetUpdate,
    HealthResponse,
)
from .repository import BudgetNotFoundError, BudgetRepository


def create_app(database_path: str | None = None) -> FastAPI:
    repository = BudgetRepository(
        database_path or os.getenv("FINANZEN_BUDGET_DB_PATH", "data/budgets.db")
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        repository.initialize()
        yield

    app = FastAPI(
        title="FinanZen Budget Service",
        version="0.1.0",
        description=(
            "Microservicio responsable de crear presupuestos, "
            "consultar su estado y calcular el uso de límites."
        ),
        lifespan=lifespan,
    )

    @app.exception_handler(BudgetNotFoundError)
    async def budget_not_found_handler(_, __):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "Budget not found"},
        )

    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["Operations"],
    )
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service="budget-service",
        )

    @app.post(
        "/api/v1/budgets",
        response_model=BudgetResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["Budgets"],
    )
    def create_budget(
        budget: BudgetCreate,
        x_user_id: str = Header(
            min_length=1,
            max_length=80,
            alias="X-User-Id",
        ),
    ) -> BudgetResponse:
        return repository.create_budget(
            x_user_id,
            budget,
        )

    @app.put(
        "/api/v1/budgets/{budget_id}",
        response_model=BudgetResponse,
        tags=["Budgets"],
    )
    def update_budget(
        budget_id: str,
        update: BudgetUpdate,
        x_user_id: str = Header(
            min_length=1,
            max_length=80,
            alias="X-User-Id",
        ),
    ) -> BudgetResponse:
        return repository.update_budget(
            x_user_id,
            budget_id,
            update,
        )

    @app.get(
        "/api/v1/budgets/{budget_id}/status",
        response_model=BudgetStatus,
        tags=["Budgets"],
    )
    def get_budget_status(
        budget_id: str,
        x_user_id: str = Header(
            min_length=1,
            max_length=80,
            alias="X-User-Id",
        ),
    ) -> BudgetStatus:
        return repository.get_budget_status(
            x_user_id,
            budget_id,
        )

    @app.get(
        "/api/v1/reports",
        response_model=list[BudgetResponse],
        tags=["Reports"],
    )
    def reports(
        x_user_id: str = Header(
            min_length=1,
            max_length=80,
            alias="X-User-Id",
        ),
    ) -> list[BudgetResponse]:
        return repository.list_budgets(x_user_id)

    @app.post(
        "/internal/events/transaction-recorded",
        tags=["Events"],
    )
    def consume_transaction_recorded(event: dict):
        return repository.process_transaction_recorded(event)

    return app


app = create_app()