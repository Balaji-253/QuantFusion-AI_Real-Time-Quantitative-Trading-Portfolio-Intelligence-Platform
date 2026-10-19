
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict


class MarketEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    symbol: str
    price: float
    volume: float
    source: str
    event_time: datetime
    received_time: datetime


class PaperOrderRequest(BaseModel):
    symbol: str = Field(
        min_length=1,
        max_length=24,
        pattern=r"^[A-Za-z0-9._-]+$",
    )
    side: Literal["BUY", "SELL"]
    quantity: int = Field(gt=0, le=100_000)
    idempotency_key: str = Field(
        min_length=16,
        max_length=128,
        pattern=r"^[A-Za-z0-9_-]+$",
    )


class PaperOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: str
    symbol: str
    side: str
    quantity: int
    requested_price: float
    filled_price: float
    notional: float
    status: str
    created_at: datetime


class SimulatorControl(BaseModel):
    enabled: bool
