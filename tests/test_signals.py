from datetime import datetime, timedelta, timezone

from app.analytics import calculate_metrics


def test_bullish_signal_threshold():
    result = calculate_metrics("TEST", [100.0, 100.1, 100.3, 100.5])

    assert result["window_return"] > 0.002
    assert result["observations"] == 4


def test_bearish_signal_threshold():
    result = calculate_metrics("TEST", [100.0, 99.9, 99.7, 99.5])

    assert result["window_return"] < -0.002
    assert result["observations"] == 4


def test_neutral_return_inside_threshold():
    result = calculate_metrics("TEST", [100.0, 100.05, 100.1])

    assert -0.002 < result["window_return"] < 0.002


def test_positive_threshold_boundary_with_float_precision():
    result = calculate_metrics("TEST", [100.0, 100.2])

    assert abs(result["window_return"] - 0.002) < 1e-12


def test_insufficient_observations_can_be_identified():
    result = calculate_metrics("TEST", [100.0, 101.0])

    assert result["observations"] == 2
    assert result["window_return"] is not None


def test_metrics_include_latest_timestamp():
    timestamps = [
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 1, tzinfo=timezone.utc)
        + timedelta(seconds=1),
    ]

    result = calculate_metrics("TEST", [100.0, 101.0], timestamps)

    assert result["latest_timestamp"] == timestamps[-1].isoformat()


from app.analytics import calculate_volatility_aware_signal


def test_volatility_aware_signal_bullish():
    result = calculate_volatility_aware_signal(0.01, 0.005, 100)
    assert result["signal"] == "BULLISH"
    assert result["score"] == 0.6667


def test_volatility_aware_signal_bearish():
    result = calculate_volatility_aware_signal(-0.01, 0.005, 100)
    assert result["signal"] == "BEARISH"
    assert result["score"] == -0.6667


def test_volatility_aware_signal_neutral_below_threshold():
    result = calculate_volatility_aware_signal(0.001, 0.005, 100)
    assert result["signal"] == "NEUTRAL"


def test_volatility_aware_signal_insufficient_observations():
    result = calculate_volatility_aware_signal(0.01, 0.005, 10)
    assert result["signal"] == "NEUTRAL"
    assert result["score"] == 0.0


def test_volatility_aware_signal_missing_volatility():
    result = calculate_volatility_aware_signal(0.01, None, 100)
    assert result["signal"] == "NEUTRAL"
    assert "unavailable" in result["reason"]


def test_volatility_aware_signal_rejects_invalid_threshold():
    import pytest

    with pytest.raises(ValueError):
        calculate_volatility_aware_signal(0.01, 0.005, 100, min_return_threshold=0)
