# TOMANAP backend

FastAPI backend for the anonymous, room-based TOMANAP multiplayer game.
Phases 1 through 7 currently provide the application foundation, pure game
rules, async persistence, secure anonymous-session rotation, the complete
lobby workflow, and an authoritative multi-round HTTP game loop with draft
editing, idempotent closure, reviews, and cumulative leaderboards. Phase 6
adds authenticated realtime events, background deadline recovery, bounded
entry-point rate limits, and correlation-aware structured audit logs. Phase 7
adds a transactional event outbox with leased dispatch, stable event IDs,
bounded exponential retry, and crash recovery.
Phase 8 adds single-use realtime tickets, reconnect resynchronization markers,
heartbeat and connection controls, atomic command idempotency, and optional
Redis-backed pub/sub and distributed entry rate limiting.
Phase 9 adds fail-closed production settings, dependency-aware readiness,
graceful WebSocket draining, bounded retention cleanup, and vendor-neutral
OpenTelemetry traces and metrics over OTLP/HTTP.
Phase 10 adds real PostgreSQL and Redis concurrency verification, strict API
request models, HTTP and WebSocket size ceilings, WebSocket Origin enforcement,
fault/recovery checks, and a configurable stateful load/soak harness.

## Local setup

Python 3.13 and [uv](https://docs.astral.sh/uv/) are required.

```powershell
uv sync --all-groups
Copy-Item .env.example .env
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

The dependency-free liveness endpoint is available at `GET /health`.
`GET /health/ready` returns `503` until the database is reachable, its Alembic
revision is current, configured Redis and workers are healthy, and the process
is accepting traffic. The response intentionally exposes only check booleans.

Lobby clients use the `X-TOMANAP-Session` header for authenticated commands.
Reconnect tokens are accepted only by `POST /sessions/restore`, where both
credentials are rotated atomically.

## Realtime contract

First call `POST /games/{room_code}/realtime-ticket` with the current session
header. Connect to `WS /ws/games/{room_code}` with exactly two WebSocket
subprotocols: `tomanap.ticket` and the returned short-lived ticket. Neither the
session token nor ticket belongs in the URL. The ticket is stored only as a
hash, bound to the room and player, and consumed atomically once.

The token-free `connection.ready` snapshot sets `resync_required` and includes
the latest durable event ID so clients explicitly reload authoritative HTTP
state after every reconnect. Clients answer `connection.ping` with `pong` and
may send `ping` to receive `connection.pong`.

Room events include `lobby.updated`, `game.started`, `submission.updated`,
`submission.finalized`, `round.started`, `round.closed`, and `game.completed`.
Submission events contain status metadata only; private answers are never
broadcast. Clients should use events as invalidation signals and retrieve the
latest authoritative HTTP state.

Every committed event is stored in `outbox_events` in the same transaction as
its domain mutation. Delivery is at least once: consumers must deduplicate by
`event_id`. An opportunistic dispatch after successful HTTP commands minimizes
latency, while the background outbox worker recovers broker failures, process
crashes, and expired worker leases.

`Idempotency-Key` is supported by game-start and round-advance commands. The
key and response commit atomically with the domain mutation; replays return the
original response with `Idempotency-Replayed: true`. Credential-issuing
commands are deliberately excluded so plaintext credentials are never cached.

When `TOMANAP_REDIS_URL` is configured, room events use Redis pub/sub and entry
rate limits use an atomic Redis sliding window shared by every API instance.
Without Redis, the bounded local adapters remain suitable for development and
unit tests.

The deadline worker runs startup recovery and periodic bounded sweeps. Its
interval and batch size, along with entry rate-limit bounds, are configurable
through the variables documented in `.env.example`.

The maintenance worker deletes expired credentials and idempotency records,
settled outbox events beyond retention, and old completed games. Every table is
processed in a bounded row-locked batch, so several instances can run it
safely. Shutdown first marks readiness unavailable, rejects new WebSockets,
signals established sockets with close code `1012`, and waits only for the
configured grace period before releasing dependencies.

Set `TOMANAP_TELEMETRY_ENABLED=true` and configure an OTLP base endpoint to
export FastAPI and SQLAlchemy traces and HTTP metrics. The backend appends
`/v1/traces` and `/v1/metrics`; an OpenTelemetry Collector can route them to
the production observability platform without backend code changes.

Production configuration fails closed unless PostgreSQL, TLS Redis, HTTPS
origins, non-local trusted hosts, all authoritative workers, disabled docs and
diagnostic logging, and an HTTPS OTLP endpoint are explicitly configured.

All request schemas reject unknown fields and implicit type coercion. HTTP
bodies are limited before parsing, including streamed bodies whose actual size
exceeds `Content-Length`. WebSockets require an exact configured browser
Origin before a one-time ticket is consumed and reject oversized or binary
client messages.

## Production-engine and load verification

The disposable integration stack is test infrastructure only; it does not
define deployment topology. Docker starts pinned PostgreSQL and Redis images,
runs the real-engine tests, and always removes the containers and volumes:

```powershell
./scripts/run_integration.ps1
```

The integration suite validates the PostgreSQL migration, cross-instance
outbox leasing, exactly-once deadline scoring, disjoint maintenance batches,
Redis atomic rate limiting and fan-out, bounded slow subscribers, and readiness
failure/recovery.

For load or soak verification, start a migrated API with rate limits sized for
the chosen test and run:

```powershell
uv run python scripts/soak.py `
  --base-url http://127.0.0.1:8000 `
  --virtual-users 4 `
  --iterations 25 `
  --max-error-rate 0.01 `
  --max-p95-ms 500
```

Each iteration creates and joins a two-player room, marks the guest ready,
starts a game with an idempotency key, and reads the authoritative round. The
JSON result contains only operation counts, sanitized failure types, latency
percentiles, and error rate; session credentials and response bodies are never
retained.

An opt-in OWASP ZAP passive baseline can scan a separately started API that is
reachable from Docker:

```powershell
./scripts/run_security_scan.ps1 `
  -Target http://host.docker.internal:58000
```

The runner writes JSON and HTML reports under `work/zap`. Configured failures
and scanner errors fail the command; warnings are preserved for human triage.
The baseline is passive and does not replace an authorized active API scan in
the final deployment environment.

## Verification

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

The database URL must use SQLAlchemy's `sqlite+aiosqlite` or
`postgresql+asyncpg` async dialect.
