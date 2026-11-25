from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: str
    event_id: str
    user_id: str
    budget_id: str
    category: str
    currency: str
    limit_amount: Decimal
    spent_amount: Decimal
    usage_percentage: Decimal
    status: str
    created_at: datetime


class HealthResponse(BaseModel):
    status: str
    service: str