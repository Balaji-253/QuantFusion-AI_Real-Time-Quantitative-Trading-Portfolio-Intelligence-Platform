from app.quant import metrics_for_prices, momentum_signal


def test_metrics_empty():
    result = metrics_for_prices([])
    assert result["observations"] == 0
    assert result["last_price"] is None


def test_metrics_basic():
    result = metrics_for_prices([100.0, 110.0, 99.0])
    assert result["observations"] == 3
    assert round(result["return_pct"], 2) == -1.0
    assert round(result["max_drawdown_pct"], 2) == -10.0


def test_signal_requires_enough_data():
    result = momentum_signal([1.0, 2.0, 3.0])
    assert result["signal"] == "INSUFFICIENT_DATA"
