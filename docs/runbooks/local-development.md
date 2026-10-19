# Local development runbook

## Startup

1. Copy `.env.example` to `.env`.
2. Choose SQLite for local Python or PostgreSQL via Docker Compose.
3. Install dependencies and run `uvicorn app.main:app --reload`.
4. Verify `/health`, `/api/v1/market/latest`, and `/docs`.

## Troubleshooting

- Database connection error: verify `DATABASE_URL`, database availability, and credentials.
- Empty latest prices: verify `ENABLE_SIMULATOR=true` and inspect application logs.
- Docker API fails to start: use `docker compose logs -f api` and `docker compose ps`.
- No signals: momentum signals require at least 20 observations for a symbol.
- Simulator prices: all default prices are synthetic, not quotes from an exchange.
