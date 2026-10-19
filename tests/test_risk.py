
import pytest

from app.config import get_settings
from app.risk import RiskRejected, validate_paper_order, validate_order


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_order_notional_limit():
    with pytest.raises(RiskRejected, match="notional"):
        validate_paper_order("BUY", 100, 550.0, 0)


def test_order_position_limit():
    with pytest.raises(RiskRejected, match="position"):
        validate_paper_order("BUY", 101, 10.0, 0)


@pytest.mark.parametrize("quantity", [0, -1])
def test_quantity_must_be_positive(quantity):
    with pytest.raises(RiskRejected, match="Quantity"):
        validate_paper_order("BUY", quantity, 10.0, 0)


@pytest.mark.parametrize("price", [0, -10.0])
def test_price_must_be_positive(price):
    with pytest.raises(RiskRejected, match="price"):
        validate_paper_order("BUY", 1, price, 0)


@pytest.mark.parametrize("side", ["", "HOLD", "INVALID"])
def test_invalid_order_side_is_rejected(side):
    with pytest.raises(RiskRejected, match="side"):
        validate_paper_order(side, 1, 10.0, 0)


def test_valid_buy_order():
    assert validate_paper_order("BUY", 2, 10.0, 0) == 20.0


def test_sell_cannot_exceed_position_limit():
    with pytest.raises(RiskRejected):
        validate_paper_order("SELL", 101, 10.0, 0)


def _fake_db():
    from types import SimpleNamespace

    class FakeQuery:
        def all(self):
            return [
                SimpleNamespace(
                    symbol="AAPL",
                    side="BUY",
                    quantity=1,
                    filled_price=950.0,
                )
            ]

    class FakeDB:
        def query(self, model):
            return FakeQuery()

    return FakeDB()


def test_buy_rejected_when_cash_is_insufficient(monkeypatch):
    from types import SimpleNamespace
    from app import risk

    settings = get_settings()
    monkeypatch.setattr(
        risk,
        "get_settings",
        lambda: SimpleNamespace(
            initial_cash=1000.0,
            max_order_notional=settings.max_order_notional,
            max_position_quantity=settings.max_position_quantity,
        ),
    )

    with pytest.raises(RiskRejected, match="Insufficient cash"):
        validate_order("AAPL", "BUY", 1, 100.0, _fake_db())


def test_buy_allowed_when_cash_is_sufficient(monkeypatch):
    from types import SimpleNamespace
    from app import risk

    settings = get_settings()
    monkeypatch.setattr(
        risk,
        "get_settings",
        lambda: SimpleNamespace(
            initial_cash=2000.0,
            max_order_notional=settings.max_order_notional,
            max_position_quantity=settings.max_position_quantity,
        ),
    )

    validate_order("AAPL", "BUY", 1, 100.0, _fake_db())


@pytest.mark.parametrize("price", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_prices_are_rejected(price):
    with pytest.raises(RiskRejected):
        validate_paper_order("BUY", 1, price, 0)


@pytest.mark.parametrize("quantity", [1.5, 2.25, float("nan"), float("inf")])
def test_non_integer_quantities_are_rejected(quantity):
    with pytest.raises(RiskRejected):
        validate_paper_order("BUY", quantity, 10.0, 0)


@pytest.mark.parametrize("position", [1.5, float("nan"), float("inf")])
def test_invalid_current_positions_are_rejected(position):
    with pytest.raises(RiskRejected):
        validate_paper_order("BUY", 1, 10.0, position)
