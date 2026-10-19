import pytest

from app import main


@pytest.mark.parametrize(
    ("window_return", "observations", "expected_signal", "expected_score"),
    [
        (0.01, 100, "BULLISH", 0.8333),
        (-0.01, 100, "BEARISH", -0.8333),
        (0.001, 100, "NEUTRAL", 0.3333),
        (0.002, 100, "BULLISH", 0.5),
        (-0.002, 100, "BEARISH", -0.5),
        (0.01, 19, "NEUTRAL", 0.0),
        (None, 100, "NEUTRAL", 0.0),
    ],
)
def test_signal_classification(
    client,
    monkeypatch,
    window_return,
    observations,
    expected_signal,
    expected_score,
):
    monkeypatch.setattr(main, "latest_cache", lambda: {"TEST": {}})

    def fake_metrics(db, symbol, window=100, lookback_minutes=60):
        return {
            "symbol": symbol,
            "latest_price": 100.0,
            "observations": observations,
            "window_return": window_return,
                "volatility": 0.002,
                "source": "synthetic",
        }

    monkeypatch.setattr(main, "get_market_metrics", fake_metrics)

    response = client.get("/api/v1/analytics/signals")

    assert response.status_code == 200, response.json()
    data = response.json()
    assert data["mode"] == "PAPER_ONLY"
    assert data["source"] == "synthetic"
    assert len(data["items"]) == 1

    signal = data["items"][0]
    assert signal["symbol"] == "TEST"
    assert signal["signal"] == expected_signal
    assert signal["score"] == expected_score
    assert signal["mode"] == "PAPER_ONLY"
    assert signal["reason"]
