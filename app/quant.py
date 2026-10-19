from math import sqrt
from sqlalchemy import select
from app.models import MarketEvent


def symbol_history(db, symbol: str, limit: int = 500) -> list[float]:
    rows = db.scalars(
        select(MarketEvent).where(MarketEvent.symbol == symbol.upper())
        .order_by(MarketEvent.id.desc()).limit(limit)
    ).all()
    return [float(row.price) for row in reversed(rows)]


def metrics_for_prices(prices: list[float]) -> dict:
    if not prices:
        return {"observations": 0, "last_price": None, "return_pct": None, "volatility_pct": None, "max_drawdown_pct": None}
    returns = [(prices[i] / prices[i - 1]) - 1 for i in range(1, len(prices)) if prices[i - 1] > 0]
    peak = prices[0]
    max_drawdown = 0.0
    for price in prices:
        peak = max(peak, price)
        if peak > 0:
            max_drawdown = min(max_drawdown, (price / peak) - 1)
    volatility = None
    if len(returns) >= 2:
        mean = sum(returns) / len(returns)
        variance = sum((x - mean) ** 2 for x in returns) / (len(returns) - 1)
        volatility = sqrt(max(0.0, variance)) * 100
    return {
        "observations": len(prices),
        "last_price": prices[-1],
        "return_pct": ((prices[-1] / prices[0]) - 1) * 100 if prices[0] else None,
        "volatility_pct": volatility,
        "max_drawdown_pct": max_drawdown * 100,
    }


def momentum_signal(prices: list[float], short_window: int = 5, long_window: int = 20) -> dict:
    if len(prices) < long_window:
        return {"signal": "INSUFFICIENT_DATA", "score": None, "observations": len(prices)}
    short_mean = sum(prices[-short_window:]) / short_window
    long_mean = sum(prices[-long_window:]) / long_window
    score = (short_mean / long_mean) - 1 if long_mean else 0.0
    signal = "BUY_BIAS" if score > 0.001 else "SELL_BIAS" if score < -0.001 else "NEUTRAL"
    return {"signal": signal, "score": score, "observations": len(prices), "short_mean": short_mean, "long_mean": long_mean}
