from datetime import datetime, timedelta, timezone
from math import sqrt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MarketEvent

DEFAULT_WINDOW = 100
MIN_OBSERVATIONS_FOR_VOLATILITY = 3


def calculate_returns(prices: list[float]) -> list[float]:
    """Calculate simple returns between consecutive positive prices."""
    returns = []
    for previous, current in zip(prices, prices[1:]):
        if previous > 0:
            returns.append(current / previous - 1.0)
    return returns


def calculate_volatility(returns: list[float]) -> float | None:
    """Sample standard deviation of returns per observation."""
    if len(returns) < MIN_OBSERVATIONS_FOR_VOLATILITY:
        return None

    mean_return = sum(returns) / len(returns)
    variance = sum(
        (value - mean_return) ** 2 for value in returns
    ) / (len(returns) - 1)

    return sqrt(variance)


def calculate_volatility_aware_signal(
    window_return: float | None,
    volatility: float | None,
    observations: int,
    min_observations: int = 20,
    min_return_threshold: float = 0.002,
) -> dict:
    """Generate an explainable research signal using return and volatility.

    This is a heuristic for synthetic-data research, not a validated
    trading prediction. Volatility is measured per observation.
    """
    if observations < min_observations:
        return {
            "signal": "NEUTRAL",
            "score": 0.0,
            "reason": "Insufficient observations for a directional signal.",
        }

    if window_return is None:
        return {
            "signal": "NEUTRAL",
            "score": 0.0,
            "reason": "Window return is unavailable.",
        }

    if volatility is None or volatility < 0:
        return {
            "signal": "NEUTRAL",
            "score": 0.0,
            "reason": "Volatility is unavailable or invalid.",
        }

    if min_return_threshold <= 0:
        raise ValueError("min_return_threshold must be positive.")

    if volatility == 0:
        normalized_return = (
            1.0 if window_return > 0
            else -1.0 if window_return < 0
            else 0.0
        )
    else:
        normalized_return = window_return / volatility

    # Smoothly map the volatility-normalized return to (-1, 1).
    # This avoids making many different signals appear exactly +/-1.
    score = normalized_return / (1.0 + abs(normalized_return))

    if abs(window_return) < min_return_threshold:
        return {
            "signal": "NEUTRAL",
            "score": round(score, 4),
            "reason": "Window return is below the minimum return threshold.",
        }

    if window_return > 0:
        signal = "BULLISH"
        reason = "Positive window return meets the threshold; score is scaled by observed volatility."
    else:
        signal = "BEARISH"
        reason = "Negative window return meets the threshold; score is scaled by observed volatility."

    return {
        "signal": signal,
        "score": round(score, 4),
        "reason": reason,
    }


def calculate_max_drawdown(prices: list[float]) -> float | None:
    """Calculate maximum peak-to-trough drawdown as a fraction."""
    if len(prices) < 2:
        return None
    if any(price <= 0 for price in prices):
        raise ValueError("Prices must be positive.")

    peak = prices[0]
    maximum_drawdown = 0.0

    for price in prices[1:]:
        peak = max(peak, price)
        maximum_drawdown = max(
            maximum_drawdown,
            (peak - price) / peak,
        )

    return maximum_drawdown


def calculate_metrics(
    symbol: str,
    prices: list[float],
    timestamps: list[datetime] | None = None,
) -> dict:
    """Calculate quantitative metrics from chronological prices."""
    if any(price <= 0 for price in prices):
        raise ValueError("Prices must be positive.")

    observations = len(prices)

    if observations == 0:
        return {
            "symbol": symbol,
            "observations": 0,
            "latest_price": None,
            "window_return": None,
            "volatility": None,
            "max_drawdown": None,
            "latest_timestamp": None,
            "source": "unavailable",
            "volatility_unit": "per_observation",
        }

    returns = calculate_returns(prices)

    window_return = (
        prices[-1] / prices[0] - 1.0
        if observations >= 2
        else None
    )

    latest_timestamp = (
        timestamps[-1].isoformat()
        if timestamps and len(timestamps) == observations
        else None
    )

    return {
        "symbol": symbol,
        "observations": observations,
        "latest_price": prices[-1],
        "window_return": window_return,
        "volatility": calculate_volatility(returns),
        "max_drawdown": calculate_max_drawdown(prices),
        "latest_timestamp": latest_timestamp,
        "source": "synthetic",
        "volatility_unit": "per_observation",
    }


def get_market_metrics(
    db: Session,
    symbol: str,
    window: int = DEFAULT_WINDOW,
    lookback_minutes: int = 60,
) -> dict:
    """Calculate metrics from recent persisted market observations."""
    if not 2 <= window <= 10000:
        raise ValueError("window must be between 2 and 10000.")

    if not 1 <= lookback_minutes <= 10080:
        raise ValueError(
            "lookback_minutes must be between 1 and 10080."
        )

    cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=lookback_minutes
    )

    statement = (
        select(MarketEvent)
        .where(
            MarketEvent.symbol == symbol.upper(),
            MarketEvent.event_time >= cutoff,
        )
        .order_by(
            MarketEvent.event_time.desc(),
            MarketEvent.id.desc(),
        )
        .limit(window)
    )

    rows = list(db.scalars(statement).all())
    rows.reverse()

    result = calculate_metrics(
        symbol.upper(),
        [float(row.price) for row in rows],
        [row.event_time for row in rows],
    )

    result["window_size"] = window
    result["lookback_minutes"] = lookback_minutes
    return result
