def test_portfolio_endpoint_returns_valuation_fields(client):
    response = client.get("/api/v1/portfolio")

    assert response.status_code == 200

    data = response.json()

    assert "cash" in data
    assert "positions" in data
    assert "market_value" in data
    assert "equity" in data
    assert "missing_price_symbols" in data
    assert "valuation_complete" in data
    assert data["mode"] == "PAPER_ONLY"
