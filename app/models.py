from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class TransactionType(str, Enum):
    INCOME = "income"
    EXPENSE = "expense"


class TransactionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    account_id: str = Field(min_length=1, max_length=80)
    type: TransactionType
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: str = Field(default="PEN", pattern=r"^[A-Z]{3}$")
    category: str = Field(min_length=1, max_length=80)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    description: str | None = Field(default=None, max_length=240)


class TransactionResponse(TransactionCreate):
    id: str
    user_id: str
    created_at: datetime


class MonthlySummary(BaseModel):
    user_id: str
    month: str
    currency: str
    income: Decimal
    expenses: Decimal
    balance: Decimal
    transaction_count: int


class HealthResponse(BaseModel):
    status: str
    service: str

