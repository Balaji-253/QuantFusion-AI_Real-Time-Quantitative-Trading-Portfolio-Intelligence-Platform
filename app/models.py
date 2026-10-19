from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, Integer, String, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MarketEvent(Base):
    __tablename__ = "market_events"
    __table_args__ = (Index("ix_market_symbol_ts", "symbol", "event_time"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    symbol: Mapped[str] = mapped_column(String(24), index=True)
    price: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[str] = mapped_column(String(40), default="synthetic")
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    received_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PaperOrder(Base):
    __tablename__ = "paper_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    symbol: Mapped[str] = mapped_column(String(24), index=True)
    side: Mapped[str] = mapped_column(String(4))
    quantity: Mapped[int] = mapped_column(Integer)
    requested_price: Mapped[float] = mapped_column(Float)
    filled_price: Mapped[float] = mapped_column(Float)
    notional: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="FILLED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
