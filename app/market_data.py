import asyncio
import math
import random
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.database import SessionLocal
from app.models import MarketEvent
from app.config import get_settings

SYMBOLS = {
    "SPY": 550.0,
    "QQQ": 470.0,
    "AAPL": 225.0,
    "MSFT": 420.0,
}
_latest: dict[str, dict] = {}
_subscribers: set[asyncio.Queue] = set()
_simulator_enabled = get_settings().enable_simulator
_price_state = dict(SYMBOLS)
_rng = random.Random(20261017)


def latest_cache() -> dict[str, dict]:
    return dict(_latest)


def simulator_status() -> bool:
    return _simulator_enabled


def set_simulator_enabled(enabled: bool) -> None:
    global _simulator_enabled
    _simulator_enabled = enabled


def subscribe() -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers.add(queue)
    return queue


def unsubscribe(queue: asyncio.Queue) -> None:
    _subscribers.discard(queue)


async def publish(event: dict) -> None:
    stale = []
    for queue in tuple(_subscribers):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            # Drop the oldest queued event to keep a slow client from blocking ingestion.
            try:
                queue.get_nowait()
                queue.put_nowait(event)
            except (asyncio.QueueEmpty, asyncio.QueueFull):
                stale.append(queue)
    for queue in stale:
        unsubscribe(queue)


def _persist_event(event: dict) -> None:
    db = SessionLocal()
    try:
        row = MarketEvent(
            event_id=event["event_id"],
            symbol=event["symbol"],
            price=event["price"],
            volume=event["volume"],
            source=event["source"],
            event_time=datetime.fromisoformat(event["event_time"]),
            received_time=datetime.now(timezone.utc),
        )
        db.add(row)
        db.commit()
    except IntegrityError:
        db.rollback()  # Duplicate event IDs are idempotently ignored.
    finally:
        db.close()


async def emit_tick(symbol: str, price: float, volume: float, source: str = "synthetic") -> dict:
    now = datetime.now(timezone.utc).isoformat()
    event = {
        "event_id": str(uuid.uuid4()),
        "symbol": symbol.upper(),
        "price": round(float(price), 4),
        "volume": float(volume),
        "source": source,
        "event_time": now,
        "received_time": datetime.now(timezone.utc).isoformat(),
    }
    _latest[event["symbol"]] = event
    await asyncio.to_thread(_persist_event, event)
    await publish(event)
    return event


async def simulator_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        if _simulator_enabled:
            for symbol in SYMBOLS:
                prior = _price_state[symbol]
                # Small seeded random walk, for pipeline testing only.
                shock = _rng.gauss(0.00005, 0.0012)
                price = max(0.01, prior * math.exp(shock))
                _price_state[symbol] = price
                await emit_tick(symbol, price, _rng.randint(10, 500), source="synthetic")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=max(0.1, get_settings().simulator_interval_seconds))
        except asyncio.TimeoutError:
            pass


def load_latest_from_db() -> None:
    db = SessionLocal()
    try:
        for symbol in SYMBOLS:
            row = db.scalar(select(MarketEvent).where(MarketEvent.symbol == symbol).order_by(MarketEvent.id.desc()).limit(1))
            if row:
                _latest[symbol] = {
                    "event_id": row.event_id, "symbol": row.symbol, "price": row.price,
                    "volume": row.volume, "source": row.source,
                    "event_time": row.event_time.isoformat(),
                    "received_time": row.received_time.isoformat(),
                }
                _price_state[symbol] = row.price
    finally:
        db.close()
