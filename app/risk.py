
import math
from numbers import Integral

from app.config import get_settings


class RiskRejected(Exception):
    """Raised when an order violates a risk limit."""


def validate_paper_order(
    side: str,
    quantity: int,
    price: float,
    current_position: int,
) -> float:
    settings = get_settings()

    if side not in {"BUY", "SELL"}:
        raise RiskRejected("Invalid order side.")

    if (
        isinstance(quantity, bool)
        or not isinstance(quantity, Integral)
        or quantity <= 0
    ):
        raise RiskRejected("Quantity must be a positive integer.")

    if isinstance(price, bool):
        raise RiskRejected("Invalid price: price must be finite and positive.")

    try:
        price = float(price)
    except (TypeError, ValueError, OverflowError) as exc:
        raise RiskRejected(
            "Invalid price: price must be finite and positive."
        ) from exc

    if not math.isfinite(price) or price <= 0:
        raise RiskRejected("Invalid price: price must be finite and positive.")

    if (
        isinstance(current_position, bool)
        or not isinstance(current_position, Integral)
    ):
        raise RiskRejected("Current position must be a finite integer.")

    notional = quantity * price

    if notional > settings.max_order_notional:
        raise RiskRejected("Order notional exceeds the configured limit.")

    if side == "SELL" and quantity > current_position:
        raise RiskRejected("Sell quantity exceeds the current position.")

    resulting_position = current_position + (
        quantity if side == "BUY" else -quantity
    )

    if abs(resulting_position) > settings.max_position_quantity:
        raise RiskRejected(
            "Resulting position exceeds the configured position limit."
        )

    return float(notional)


def validate_order(symbol, side, quantity, price, db) -> None:
    from app.models import PaperOrder

    settings = get_settings()
    orders = db.query(PaperOrder).all()
    symbol = symbol.upper()

    # Calculate the current position for this symbol.
    position = sum(
        order.quantity if order.side == "BUY" else -order.quantity
        for order in orders
        if order.symbol.upper() == symbol
    )

    # Reconstruct available cash from the persisted order ledger.
    cash = float(settings.initial_cash)

    for order in orders:
        signed_quantity = (
            order.quantity if order.side == "BUY" else -order.quantity
        )
        cash -= signed_quantity * float(order.filled_price)

    notional = validate_paper_order(
        side=side,
        quantity=quantity,
        price=price,
        current_position=position,
    )

    if side == "BUY" and notional > cash:
        raise RiskRejected("Insufficient cash for this order.")
