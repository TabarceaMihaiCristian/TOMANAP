# TOMANAP Project Handoff

This document contains the relevant context and decisions from the planning
session for continuing implementation in the Codex app.

## Project Location

- Repository root: `C:\Users\mitabarcea\..MihaiTabarcea\Personal_stuff\tomanap`
- Backend root: `backend/`
- Backend package: `backend/app/`
- The repository was not initialized as a Git repository when last inspected.

## Product Description

TOMANAP is a real-time multiplayer adaptation of a Romanian paper game. It is
intended to work well on phones and should use a room-based experience similar
to Skribbl.io or Gartic Phone. It must not require registration or user
accounts.

The name represents seven answer categories:

| Letter | Romanian category | English meaning |
| --- | --- | --- |
| T | Tari | Countries |
| O | Orase | Cities |
| M | Marci | Brands |
| A | Activitati | Activities |
| N | Nume | Names |
| A | Animale | Animals |
| P | Plante | Plants |

The expected room size is 2-6 players. Supporting up to 8 players may be added
later, but the first implementation should optimize and test for 2-6.

## Game Rules

1. A host creates a room and shares its room code or link.
2. Other players join using a display name. No email, password, or account is
   required.
3. At the beginning of a round, one unused alphabet letter is selected. The
   original paper game has one player mentally recite the alphabet until
   another player says stop. The digital version can reproduce this through a
   server-controlled randomized or cycling letter selector.
4. Players receive 60 seconds by default to submit one answer for each of the
   seven categories.
5. Every valid answer must begin with the round's selected letter.
6. When time expires, or all players have submitted, answers are compared per
   category after normalization.
7. A valid answer not shared by another player earns 10 points.
8. A valid answer shared by two or more players earns 5 points for each player
   who submitted it.
9. Empty, invalid, or late answers earn 0 points.
10. A used letter is burned and cannot be used again in the same game.
11. A game can contain a host-configured number of rounds, up to the number of
    supported letters. No game should exceed 26 rounds under the current rule.
12. Cumulative scores are displayed as a leaderboard after each round and at
    the end of the game.

Example for the letter `P`:

`Polonia | Ploiesti | Pagani | Ping-Pong | Petru | Pinguin | Papadie`

## Confirmed Architecture Decisions

- Python and FastAPI are the backend foundation.
- Use SQLAlchemy 2.x for persistence and Alembic for migrations.
- Use Pydantic schemas at API boundaries.
- The server is authoritative for room membership, letters, timers, state
  transitions, submissions, validation, and scoring.
- Use HTTP for commands and initial state retrieval.
- Use WebSockets to broadcast lobby and game events in real time.
- The game has anonymous player sessions, not authentication accounts.
- Creating or joining a room should issue opaque, high-entropy session and
  reconnect tokens. Store token hashes, never plaintext tokens, in persistent
  storage.
- A reconnect token restores the same player seat after a refresh or temporary
  connection loss.
- Host-only actions are capability checks based on room membership and the
  current player session. They are not account roles.
- Store an authoritative `ends_at` timestamp for active rounds. A browser timer
  is only a visual projection of server time.
- Round finalization must be idempotent so simultaneous workers or requests
  cannot score a round twice.
- APScheduler may be useful for cleanup jobs, but it should not be the only
  source of truth for round deadlines.
- Start with in-process WebSocket connection management. Introduce Redis
  Pub/Sub when deploying multiple backend instances.
- PostgreSQL is the intended production database. SQLite may be used for early
  local development and isolated tests if its concurrency limitations are
  understood.

## Suggested State Machines

Game states:

`LOBBY -> IN_PROGRESS -> COMPLETED`

Round states:

`PENDING -> COUNTDOWN -> ACTIVE -> REVIEW -> COMPLETED`

Important invariants:

- Only the host can configure or start a lobby.
- A game cannot start with fewer than two active players.
- A letter can appear in at most one round in a game.
- A player can have at most one submission per round.
- Submitted answers should become immutable when the player finalizes them or
  when the deadline expires.
- Scores can be calculated only once for a finalized round.
- Every state-changing operation must verify the current game and round state.

## Current Repository State

The project currently contains a package scaffold. Most modules contain only a
module-level docstring describing their responsibility. They are not functional
implementations yet.

The current `backend/pyproject.toml` specifies Python 3.13 or newer and includes:

- FastAPI
- Pydantic
- SQLAlchemy
- Alembic
- Uvicorn
- python-dotenv
- Ruff

Testing, PostgreSQL, and async database dependencies still need to be added.
Likely additions include `pytest`, `pytest-asyncio`, `httpx`, and either
`asyncpg` or `psycopg` depending on the selected SQLAlchemy session style.

There are misspelled package marker files named `__inti__.py` alongside valid
`__init__.py` files. The misspelled files should be removed during cleanup after
confirming they contain no user code.

Existing module groups:

```text
backend/app/
|-- main.py
|-- api/
|   |-- dependencies.py
|   |-- errors.py
|   |-- routes.py
|   `-- routers/
|       |-- games.py
|       |-- health.py
|       |-- invitations.py
|       |-- leaderboards.py
|       |-- lobbies.py
|       |-- players.py
|       |-- rounds.py
|       |-- sessions.py
|       |-- submissions.py
|       `-- websocket.py
|-- core/
|   |-- config.py
|   |-- constants.py
|   |-- exceptions.py
|   |-- logging.py
|   `-- security.py
|-- db/
|   |-- base.py
|   `-- session.py
|-- models/
|   |-- game.py
|   |-- invitation.py
|   |-- player.py
|   |-- round.py
|   |-- score.py
|   |-- session.py
|   `-- submission.py
|-- repositories/
|   |-- games.py
|   |-- invitations.py
|   |-- players.py
|   |-- rounds.py
|   |-- scores.py
|   |-- sessions.py
|   `-- submissions.py
|-- schemas/
|   |-- common.py
|   |-- game.py
|   |-- invitation.py
|   |-- leaderboard.py
|   |-- player.py
|   |-- round.py
|   |-- session.py
|   `-- submission.py
|-- services/
|   |-- game_lifecycle.py
|   |-- invitations.py
|   |-- leaderboards.py
|   |-- letters.py
|   |-- realtime.py
|   |-- rounds.py
|   |-- scoring.py
|   |-- sessions.py
|   |-- submissions.py
|   |-- timers.py
|   `-- validation.py
`-- utilities/
    |-- datetime.py
    |-- pagination.py
    |-- slugs.py
    `-- text.py
```

Authentication-oriented user modules were deliberately removed. Do not add
password login, email registration, account profiles, or account JWT flows
unless product requirements explicitly change.

## Recommended Implementation Order

### Phase 1: Application Foundation

1. Finalize dependencies and development tooling.
2. Implement typed settings, environment loading, logging, and constants.
3. Configure SQLAlchemy sessions and Alembic.
4. Create the FastAPI application factory/lifespan, route aggregation, error
   handlers, CORS, and `/health` endpoint.
5. Add a test application and database fixtures.

Acceptance criteria: the API starts, the health endpoint succeeds, migrations
run on an empty database, and the base test suite runs locally.

### Phase 2: Pure Game Rules

1. Define categories, scores, player limits, round duration, and alphabet
   policy in `core/constants.py`.
2. Implement answer normalization in `utilities/text.py`.
3. Implement burned-letter selection in `services/letters.py`.
4. Implement format and starting-letter validation in
   `services/validation.py`.
5. Implement category-by-category duplicate comparison and scoring in
   `services/scoring.py`.
6. Add exhaustive unit tests before connecting these services to the database.

Acceptance criteria: unique answers score 10, duplicate normalized answers
score 5, invalid/blank answers score 0, and no burned letter can be selected.

### Phase 3: Persistence Model

1. Implement enums and SQLAlchemy models for `Game`, `Player`, `Session`,
   `Round`, `Submission`, and `Score`.
2. Define unique constraints and indexes for room codes, token hashes, player
   membership, round numbers, and one submission per player per round.
3. Decide whether `Invitation` is needed for version one. A room code may make
   a separate invitation table unnecessary.
4. Generate and review the initial migration.
5. Implement repository methods with explicit transaction boundaries.

Acceptance criteria: a complete room, round, answer, and score graph can be
created, queried, and safely constrained by the database.

### Phase 4: Anonymous Sessions and Lobby

1. Implement secure room-code and token generation.
2. Implement create-room, join-room, reconnect, ready/unready, leave-room, and
   host configuration operations.
3. Hash tokens before persistence and compare them in constant time.
4. Prevent duplicate names in one room using the chosen case/diacritic policy.
5. Establish host disconnect and host-transfer behavior.
6. Add lobby API integration tests.

Acceptance criteria: 2-6 anonymous players can join a room, reconnect to their
seat, change readiness, and start only when lobby conditions are valid.

### Phase 5: Round Lifecycle and Submissions

1. Implement host-controlled game start and automatic first-round creation.
2. Broadcast the selected letter and authoritative deadline.
3. Accept one submission containing all seven category fields.
4. Permit updates until final submission or deadline, depending on the chosen
   UX policy.
5. Close a round when all active players finalize or when `ends_at` passes.
6. Score the round transactionally and expose the review payload.
7. Start the next round or complete the game.

Acceptance criteria: a full multi-round game can be played through HTTP without
WebSockets, including correct scoring and final leaderboard.

### Phase 6: Real-Time Transport

1. Implement a room-scoped WebSocket connection manager.
2. Authenticate the socket using the anonymous session token.
3. Define versioned event envelopes and payload schemas.
4. Broadcast state changes rather than allowing sockets to mutate state
   directly at first. Keep commands in tested HTTP service paths.
5. Add heartbeat, disconnect, reconnect, and stale connection handling.
6. Add WebSocket integration tests with multiple clients.

Recommended events:

- `player_joined`
- `player_left`
- `player_reconnected`
- `lobby_updated`
- `game_started`
- `round_started`
- `round_closed`
- `review_ready`
- `leaderboard_updated`
- `game_completed`
- `host_changed`
- `error`

Acceptance criteria: all connected clients observe the same ordered room state
through join, start, round, review, and completion.

### Phase 7: Reliability and Production Readiness

1. Add rate limits for room creation, joining, submissions, and socket
   connections.
2. Validate CORS and WebSocket origins against configured frontend origins.
3. Add input length and request/message-size limits.
4. Add structured logs with game, player, and round identifiers, excluding raw
   tokens.
5. Add cleanup for expired sessions and abandoned rooms.
6. Add concurrency tests for deadline submissions and duplicate finalization.
7. Add Docker configuration, PostgreSQL, deployment health checks, migrations
   on deployment, backups, metrics, and error reporting.
8. Add Redis only when multiple application instances are required.

## API Surface to Implement

Exact paths may be adjusted to existing router conventions, but the behavior
should cover:

```text
POST   /games                       Create room and host session
GET    /games/{room_code}           Read public room/game state
POST   /games/{room_code}/join      Join with display name
POST   /sessions/restore            Restore an anonymous player seat
POST   /games/{room_code}/ready     Set ready state
POST   /games/{room_code}/leave     Leave room
PATCH  /games/{room_code}/settings  Host updates settings
POST   /games/{room_code}/start     Host starts game
GET    /games/{room_code}/rounds/current
PUT    /rounds/{round_id}/submission
POST   /rounds/{round_id}/submission/finalize
GET    /rounds/{round_id}/review
GET    /games/{room_code}/leaderboard
WS     /ws/games/{room_code}
GET    /health
```

Use an opaque session token in a header or secure cookie. Make the transport
choice consistent across HTTP and WebSocket handshakes. Do not place reconnect
tokens in normal logs or long-lived URLs.

## Answer Validation Policy

Version one should automatically validate only objective rules:

- The answer is non-empty.
- It is within the configured length limit.
- Its normalized form begins with the selected letter.
- It was submitted before the authoritative deadline.

Do not attempt to build a perfect dictionary for countries, cities, brands,
activities, names, animals, and plants in the initial version. Categories such
as brands and names cannot be reliably validated from a static dictionary.

A later version can add player challenges or voting during review. Keep scoring
and review structures extensible enough to recalculate a disputed category, but
do not implement that workflow until the base game loop is stable.

## Normalization Requirements

Normalization must be centralized and tested. At minimum:

- Trim leading and trailing whitespace.
- Collapse repeated internal whitespace.
- Compare case-insensitively.
- Define a deliberate Romanian diacritic policy.
- Preserve the original answer for display while storing or deriving a
  normalized value for comparison.
- Treat punctuation and hyphens consistently, especially for multi-word names.

Do not scatter ad hoc `.lower()` comparisons across repositories or routes.

## Testing Priorities

1. Normalization, including Romanian diacritics.
2. Unique and duplicate scoring per category.
3. Empty, invalid, and late submissions.
4. Burned letters and round-count limits.
5. Invalid state transitions and host-only operations.
6. Anonymous session restoration and token rotation.
7. Transactional, idempotent round closure.
8. Multiple players submitting at the deadline.
9. WebSocket join, disconnect, reconnect, and broadcast behavior.
10. End-to-end games with 2, 6, and eventually 8 players.

## Open Product Decisions

Resolve these before their corresponding implementation phase. Sensible
defaults are included so work can continue without blocking prematurely.

- Romanian alphabet: define exactly which letters are selectable and whether
  `A` and `Ă`/`Â`, `I` and `Î`, `S` and `Ș`, and `T` and `Ț` are distinct.
  Suggested first version: use the 26 basic Latin letters and normalize
  diacritics for initial-letter and duplicate comparison.
- Letter selection: random unused letter, visible cycling selector stopped by a
  player, or server-selected letter. Suggested first version: uniformly random
  unused letter selected by the server.
- Early completion: close immediately when everyone finalizes or always wait
  for the timer. Suggested first version: close when everyone finalizes.
- Submission editing: allow edits until explicit finalization. Suggested first
  version: yes.
- Host disconnect: pause, transfer host, or allow a grace period. Suggested
  first version: retain host for a short reconnect grace period, then transfer
  to the longest-connected active player.
- Duplicate display names: reject or append a suffix. Suggested first version:
  reject normalized duplicates within one room.
- Answer disputes: no disputes, host moderation, or group voting. Suggested
  first version: no semantic validation or disputes; add group voting later.
- Persistence lifetime: decide how long completed games and abandoned lobbies
  remain stored. Suggested first version: expire abandoned lobbies after 24
  hours and retain completed games briefly for debugging, with configurable
  cleanup.

## First Codex Implementation Task

Start with Phase 1 and Phase 2 rather than implementing every module at once.
Inspect the existing files and preserve their intended package boundaries.

Suggested prompt for the next Codex session:

> Read `CODEX_HANDOFF.md` and inspect the existing backend scaffold. Implement
> Phase 1 (application foundation) and Phase 2 (pure game rules) end to end.
> Preserve the anonymous, account-free room model. Add focused tests, run them,
> run Ruff, and report any product assumptions you had to make. Do not begin the
> database domain models until the first two phases pass verification.

## Completion Definition for the MVP Backend

The MVP backend is complete when 2-6 anonymous players can create and join a
room, reconnect after refresh, play the configured number of timed rounds
without repeated letters, submit seven answers per round, receive deterministic
scores, review answers, and see a synchronized final leaderboard. The game must
remain correct under duplicate requests, temporary disconnects, and submissions
arriving close to the deadline.
