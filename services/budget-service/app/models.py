from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class BudgetCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    category: str = Field(min_length=1, max_length=80)
    limit_amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: str = Field(default="PEN", pattern=r"^[A-Z]{3}$")
    period: str = Field(default="monthly", pattern=r"^(weekly|monthly)$")


class BudgetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    category: str | None = Field(default=None, min_length=1, max_length=80)
    limit_amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    period: str | None = Field(default=None, pattern=r"^(weekly|monthly)$")


class BudgetResponse(BaseModel):
    id: str
    user_id: str
    name: str
    category: str
    limit_amount: Decimal
    currency: str
    period: str
    spent_amount: Decimal
    remaining_amount: Decimal
    usage_percentage: Decimal


class BudgetStatus(BaseModel):
    budget_id: str
    user_id: str
    limit_amount: Decimal
    spent_amount: Decimal
    remaining_amount: Decimal
    usage_percentage: Decimal
    threshold_reached: bool


class HealthResponse(BaseModel):
    status: str
    service: str