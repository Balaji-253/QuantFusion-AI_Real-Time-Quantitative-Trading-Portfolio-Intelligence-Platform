import asyncio
import hashlib
import logging
from contextlib import asynccontextmanager
from hmac import compare_digest

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    WebSocket,
)
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.analytics import get_market_metrics, calculate_volatility_aware_signal
from app.database import Base, engine, get_db
from app.market_data import (
    latest_cache,
    load_latest_from_db,
    set_simulator_enabled,
    simulator_loop,
    simulator_status,
)
from app.models import PaperOrder
from app.portfolio import portfolio_snapshot
from app.risk import RiskRejected, validate_order
from app.schemas import PaperOrderRequest, SimulatorControl


logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------
# Application lifecycle
# ---------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    await asyncio.to_thread(load_latest_from_db)

    stop_event = asyncio.Event()
    simulator_task = asyncio.create_task(
        simulator_loop(stop_event)
    )

    try:
        yield
    finally:
        stop_event.set()
        await simulator_task


# ---------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------

app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
)


# ---------------------------------------------------------
# CORS configuration
# Allows the local React/Vite frontend to access the API.
# ---------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# Order serialization
# ---------------------------------------------------------

def serialize_order(order):
    return {
        "id": str(order.id),
        "order_id": order.order_id,
        "symbol": order.symbol,
        "side": order.side,
        "quantity": order.quantity,
        "requested_price": order.requested_price,
        "filled_price": order.filled_price,
        "notional": order.notional,
        "status": order.status,
        "created_at": order.created_at,
        "mode": "PAPER_ONLY",
    }


# ---------------------------------------------------------
# Health check
# ---------------------------------------------------------

@app.get("/health", tags=["system"])
def health():
    from sqlalchemy import text

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        database_status = "ok"

    except Exception:
        logger.exception("Database health check failed")
        database_status = "error"

    return {
        "status": (
            "ok" if database_status == "ok" else "degraded"
        ),
        "database": database_status,
        "environment": settings.app_env,
        "mode": "paper_only",
    }


# ---------------------------------------------------------
# Market data
# ---------------------------------------------------------

@app.get("/api/v1/market/latest", tags=["market"])
def market_latest():
    return {
        "items": list(latest_cache().values()),
        "source": "synthetic",
    }


@app.get("/api/v1/market/symbols", tags=["market"])
def market_symbols():
    return {
        "symbols": sorted(latest_cache().keys())
    }


# ---------------------------------------------------------
# Analytics
# Note: these are baseline outputs, not trained predictions.
# ---------------------------------------------------------

@app.get("/api/v1/analytics/metrics", tags=["analytics"])
def analytics_metrics(
    symbol: str | None = None,
    window: int = 100,
    lookback_minutes: int = 60,
    db: Session = Depends(get_db),
):
    symbols = [symbol.upper()] if symbol else sorted(latest_cache().keys())

    try:
        items = [
            get_market_metrics(
                db,
                current_symbol,
                window=window,
                lookback_minutes=lookback_minutes,
            )
            for current_symbol in symbols
        ]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "items": items,
        "source": "synthetic",
        "mode": "PAPER_ONLY",
    }


@app.get("/api/v1/analytics/signals", tags=["analytics"])
def analytics_signals(
    db: Session = Depends(get_db),
    window: int = 100,
    lookback_minutes: int = 60,
):
    symbols = sorted(latest_cache().keys())
    items = []
    return_threshold = 0.002

    for current_symbol in symbols:
        try:
            metrics = get_market_metrics(
                db,
                current_symbol,
                window=window,
                lookback_minutes=lookback_minutes,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        classification = calculate_volatility_aware_signal(
            window_return=metrics["window_return"],
            volatility=metrics["volatility"],
            observations=metrics["observations"],
            min_observations=20,
            min_return_threshold=return_threshold,
        )

        items.append({
            "symbol": current_symbol,
            "price": metrics["latest_price"],
            "signal": classification["signal"],
            "score": classification["score"],
            "reason": classification["reason"],
            "source": metrics["source"],
            "observations": metrics["observations"],
            "window_return": metrics["window_return"],
            "volatility": metrics["volatility"],
            "threshold": return_threshold,
            "mode": "PAPER_ONLY",
        })

    return {
        "items": items,
        "source": "synthetic",
        "method": "volatility_aware_window_return",
        "mode": "PAPER_ONLY",
    }


@app.get("/api/v1/portfolio", tags=["portfolio"])
def get_portfolio(db: Session = Depends(get_db)):
    return portfolio_snapshot(db)


# ---------------------------------------------------------
# Paper order history
# ---------------------------------------------------------

@app.get("/api/v1/orders", tags=["orders"])
def list_orders(db: Session = Depends(get_db)):
    orders = (
        db.query(PaperOrder)
        .order_by(PaperOrder.id.desc())
        .limit(100)
        .all()
    )

    return {
        "items": [
            serialize_order(order)
            for order in orders
        ],
        "mode": "PAPER_ONLY",
    }


# ---------------------------------------------------------
# Paper order execution
# ---------------------------------------------------------

@app.post("/api/v1/orders/paper", tags=["orders"])
def create_paper_order(
    request: PaperOrderRequest,
    db: Session = Depends(get_db),
):
    symbol = request.symbol.upper()

    # Create a deterministic order ID from the idempotency key.
    key_hash = hashlib.sha256(
        request.idempotency_key.encode("utf-8")
    ).hexdigest()

    stable_order_id = f"idem_{key_hash}"

    # Return an existing order when the same request is repeated.
    existing = (
        db.query(PaperOrder)
        .filter(
            PaperOrder.order_id == stable_order_id
        )
        .first()
    )

    if existing:
        same_request = (
            existing.symbol == symbol
            and existing.side == request.side
            and existing.quantity == request.quantity
        )

        if not same_request:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Idempotency key already used "
                    "for a different order."
                ),
            )

        return serialize_order(existing)

    # Use the latest simulated price.
    item = latest_cache().get(symbol)

    if not item or item.get("price") is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No current market price available "
                f"for {symbol}."
            ),
        )

    import math

    try:
        price = float(item["price"])
    except (TypeError, ValueError, OverflowError):
        raise HTTPException(status_code=503, detail="Market price is invalid or unavailable.")

    if not math.isfinite(price) or price <= 0:
        raise HTTPException(status_code=503, detail="Market price is invalid or unavailable.")

    # Validate risk limits before execution.
    try:
        validate_order(
            symbol,
            request.side,
            request.quantity,
            price,
            db,
        )

    except RiskRejected as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    # Record a simulated fill in the database.
    order = PaperOrder(
        order_id=stable_order_id,
        symbol=symbol,
        side=request.side,
        quantity=request.quantity,
        requested_price=price,
        filled_price=price,
        notional=price * request.quantity,
        status="FILLED",
    )

    try:
        db.add(order)
        db.commit()
        db.refresh(order)

        return serialize_order(order)

    except IntegrityError:
        db.rollback()

        # Handle a concurrent request using the same key.
        existing = (
            db.query(PaperOrder)
            .filter(
                PaperOrder.order_id == stable_order_id
            )
            .first()
        )

        if existing:
            same_request = (
                existing.symbol == symbol
                and existing.side == request.side
                and existing.quantity == request.quantity
            )

            if same_request:
                return serialize_order(existing)

            raise HTTPException(
                status_code=409,
                detail=(
                    "Idempotency key already used "
                    "for a different order."
                ),
            )

        logger.exception(
            "Order integrity constraint failed"
        )

        raise HTTPException(
            status_code=409,
            detail=(
                "Order could not be created because "
                "of a database constraint."
            ),
        )

    except Exception as exc:
        db.rollback()

        logger.exception(
            "Failed to persist paper order"
        )

        raise HTTPException(
            status_code=500,
            detail="Paper order could not be persisted.",
        ) from exc


# ---------------------------------------------------------
# Protected simulator control
# ---------------------------------------------------------

@app.post(
    "/api/v1/system/simulator",
    tags=["operations"],
)
def control_simulator(
    request: SimulatorControl,
    x_admin_token: str | None = Header(default=None),
):
    expected = settings.admin_api_token

    if (
        not expected
        or not x_admin_token
        or not compare_digest(
            x_admin_token,
            expected,
        )
    ):
        raise HTTPException(
            status_code=401,
            detail="Valid admin token required.",
        )

    set_simulator_enabled(request.enabled)

    return {
        "simulator_enabled": simulator_status(),
        "note": "Administrative simulator control.",
    }


# ---------------------------------------------------------
# Market WebSocket
# ---------------------------------------------------------

@app.websocket("/ws/market")
async def market_websocket(websocket: WebSocket):
    await websocket.accept()

    try:
        while True:
            await websocket.send_json({
                "items": list(
                    latest_cache().values()
                ),
                "source": "synthetic",
            })

            await asyncio.sleep(1)

    except Exception:
        logger.debug(
            "Market WebSocket disconnected"
        )