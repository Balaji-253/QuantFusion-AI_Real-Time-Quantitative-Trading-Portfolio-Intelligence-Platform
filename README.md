# QuantFusion AI

A Python-first, production-oriented foundation for real-time quantitative market intelligence. It includes market-event simulation/replay, quantitative metrics, a baseline ML signal, risk checks, paper orders, REST/WebSocket APIs, PostgreSQL support, Docker Compose, tests, and operational documentation.

> **Important:** This release is for research and paper trading only. It does not connect to a brokerage or submit live orders. Simulated prices are not real market data and model outputs are not investment advice.

## Architecture

```text
Synthetic / Replay Provider
          |
          v
Market Ingestion + Validation ---> MarketEvent
          |                              |
          v                              v
 SQL database (Postgres/SQLite)    In-process WebSocket fan-out
          |
          +--> Quant metrics (returns, volatility, drawdown)
          +--> Baseline signal (momentum rule; ML extension point)
          +--> Risk checks --> Paper order ledger
                                      |
                                      v
                              FastAPI REST + WebSocket
```

The first milestone is intentionally a runnable vertical slice. For multi-instance production deployment, replace the in-process fan-out with Kafka/Redis pub-sub, add a dedicated stream processor, use managed secrets, and deploy behind TLS with authentication and rate limits.

## Requirements

- Python 3.12+
- Docker Desktop + Docker Compose (recommended), or local Python environment
- Git

## Quick start with Docker

1. Copy `.env.example` to `.env`.
2. Run:

   ```bash
   docker compose up --build
   ```

3. Open:
   - Dashboard: http://localhost:3000
   - API docs: http://localhost:8000/docs
   - Health: http://localhost:8000/health
   - Latest prices: http://localhost:8000/api/v1/market/latest
   - Metrics: http://localhost:8000/api/v1/analytics/metrics
   - Signals: http://localhost:8000/api/v1/analytics/signals
   - WebSocket: `ws://localhost:8000/ws/market`

Docker Compose starts PostgreSQL and the API. The simulator is enabled by default, generating **synthetic** events to exercise the pipeline. The React dashboard is served at port 3000.

## Local Python start (SQLite)

From the repository root, in Git Bash:

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set:
`DATABASE_URL=sqlite:///./quantfusion.db`

Then run:

```bash
uvicorn app.main:app --reload
```

For PowerShell activation, use `.venv\Scripts\Activate.ps1`.

## API overview

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness and database connectivity |
| GET | `/api/v1/market/latest` | Latest event per configured symbol |
| GET | `/api/v1/market/history/{symbol}` | Recent persisted ticks for a symbol |
| GET | `/api/v1/analytics/metrics` | Returns/volatility/drawdown summary |
| GET | `/api/v1/analytics/signals` | Baseline momentum research signals |
| GET | `/api/v1/portfolio` | Paper portfolio cash, positions, equity |
| GET | `/api/v1/orders` | Paper-order ledger |
| POST | `/api/v1/orders/paper` | Submit a simulated market order after risk checks |
| POST | `/api/v1/system/simulator` | Enable/disable simulator (local/dev control) |
| WS | `/ws/market` | Stream normalized market events |

Order request example:

```json
{
  "symbol": "AAPL",
  "side": "BUY",
  "quantity": 1
}
```

Paper orders are filled against the latest available simulated/event price. This simplified fill model is not suitable for execution research until spread, latency, partial fills, fees, market impact, and order-book behavior are modeled.

## Tests

```bash
pytest -q
```

The test suite uses a temporary SQLite database. For a local environment, the following check can also validate syntax:

```bash
python -m compileall app tests
```

## Configuration

See `.env.example`. `DATABASE_URL` supports SQLite for local development and PostgreSQL for Docker. `ENABLE_SIMULATOR=true` creates synthetic events. Set it to `false` when integrating a real licensed provider.

## Production hardening checklist

- [ ] Replace synthetic provider with a licensed provider adapter and provider-specific reconnect/backoff logic.
- [ ] Add auth (OIDC/JWT), RBAC, rate limits, TLS, and tenant isolation before exposing publicly.
- [ ] Move WebSocket fan-out to Kafka/Redis for multiple API replicas.
- [ ] Use migrations (Alembic), not `create_all`, for schema evolution.
- [ ] Add idempotency keys and transactional outbox for order commands.
- [ ] Add market calendar, timezone/session handling, sequence/gap detection, and stale-data gates.
- [ ] Validate strategy with point-in-time data, walk-forward evaluation, fees, slippage, and realistic fills.
- [ ] Add Prometheus metrics, OpenTelemetry tracing, alerting, backups, restore drills, and load/chaos tests.
- [ ] Deploy via infrastructure-as-code with secrets manager and least-privilege IAM.
- [ ] Keep live brokerage execution disabled until formal risk, reconciliation, and operational review.

## License

Choose and add a license before public distribution.
