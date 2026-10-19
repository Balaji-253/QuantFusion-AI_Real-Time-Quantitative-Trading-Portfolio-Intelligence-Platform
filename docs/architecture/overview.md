# Architecture and operational boundaries

## Current release

- FastAPI application, SQLAlchemy persistence, PostgreSQL in Compose / SQLite for local runs.
- Synthetic deterministic random-walk feed, explicitly marked `source=synthetic`.
- One API process and in-process WebSocket queues. This is suitable for a single-instance initial release, not horizontal fan-out.
- Quant descriptive metrics and a baseline moving-average momentum rule.
- Paper order ledger with notional and position limits.

## Before multi-replica production

1. Introduce Kafka topics for normalized market events and order commands.
2. Define versioned Avro/Protobuf/JSON Schema contracts and compatibility rules.
3. Use consumer groups, idempotency, dead-letter queues, replay, and gap detection.
4. Move stream state to a distributed processor or dedicated service.
5. Replace schema `create_all` with Alembic migrations.
6. Move simulator control behind authenticated admin authorization or remove it.
7. Add auth, rate limits, CSRF protections where applicable, strict CORS, TLS, secrets manager, audit logging.
8. Use transactional order state machine, idempotency keys, and reconciliation.
9. Establish SLOs, dashboards, alerts, backup policy, and recovery drills.
10. Perform security, load, failure-injection, and model validation before production use.
