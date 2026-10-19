from collections import defaultdict

from sqlalchemy import select

from app.config import get_settings
from app.models import PaperOrder
from app.market_data import latest_cache


def portfolio_snapshot(db) -> dict:
    cash = float(get_settings().initial_cash)
    positions: dict[str, int] = defaultdict(int)

    orders = db.scalars(
        select(PaperOrder).order_by(PaperOrder.id.asc())
    ).all()

    for order in orders:
        signed_qty = (
            order.quantity
            if order.side == "BUY"
            else -order.quantity
        )
        positions[order.symbol] += signed_qty
        cash -= signed_qty * float(order.filled_price)

    prices = latest_cache()
    holdings = {}
    market_value = 0.0
    missing_prices = []

    for symbol, quantity in positions.items():
        if quantity == 0:
            continue

        market_event = prices.get(symbol)
        if not market_event or market_event.get("price") is None:
            missing_prices.append(symbol)
            continue

        price = float(market_event["price"])
        value = quantity * price

        holdings[symbol] = {
            "quantity": quantity,
            "last_price": price,
            "market_value": round(value, 2),
        }
        market_value += value

    return {
        "cash": round(cash, 2),
        "positions": holdings,
        "market_value": round(market_value, 2),
        "equity": round(cash + market_value, 2),
        "missing_price_symbols": sorted(missing_prices),
        "valuation_complete": len(missing_prices) == 0,
        "mode": "PAPER_ONLY",
    }