# PulseChat — Real-Time Team Chat API
### Complete Build Journal: From Zero to Production-Ready Backend

> Built with FastAPI · PostgreSQL · Redis · WebSockets · Docker · GCP Cloud Run

---

## Table of Contents

1. [What is PulseChat?](#1-what-is-pulsechat)
2. [Why This Project?](#2-why-this-project)
3. [Tech Stack — Every Tool Explained](#3-tech-stack--every-tool-explained)
4. [System Architecture — All 7 Layers](#4-system-architecture--all-7-layers)
5. [Database Design](#5-database-design)
6. [The 4 Hard Engineering Problems](#6-the-4-hard-engineering-problems)
7. [Project Folder Structure](#7-project-folder-structure)
8. [Environment Setup](#8-environment-setup)
9. [Day-by-Day Build Log](#9-day-by-day-build-log)
10. [API Reference](#10-api-reference)
11. [WebSocket Event Reference](#11-websocket-event-reference)
12. [Redis Key Design](#12-redis-key-design)
13. [Key Concepts Learned](#13-key-concepts-learned)
14. [Common Errors & Fixes](#14-common-errors--fixes)
15. [Remaining Build Plan](#15-remaining-build-plan)
16. [Resume Bullet Points](#16-resume-bullet-points)
17. [Interview Questions](#17-interview-questions)

---

## 1. What is PulseChat?

PulseChat is a **production-ready, real-time team chat API** — the backend equivalent of Slack. It is a multi-tenant system where companies (called workspaces) sign up, create channels, and let their members message each other in real time.

### In plain English

A business owner signs up on PulseChat. Their account creates a **workspace**. Inside that workspace they create **channels** (like `#general`, `#engineering`). Team members join the workspace and connect via the app. When one member sends a message in a channel, every other member in that channel receives it **instantly** — without refreshing, without polling, without any delay.

### What it is NOT

- Not a frontend/UI — this is a pure **API backend**
- Not a consumer app like WhatsApp — it is a **B2B SaaS API**
- Not a toy CRUD app — it uses real production patterns

### Slack Concepts → PulseChat Code

| What you see in Slack | What it is in your code |
|---|---|
| Workspace "TaxBuddy HQ" | One row in the `workspaces` table |
| Channel `#general` | One row in the `channels` table |
| Message from Vishal | One row in the `messages` table |
| Green dot (online) | A Redis key with 60s TTL |
| "Priya is typing..." | A Redis key with 5s TTL + WebSocket broadcast |
| Thread "2 replies" | Messages with `parent_id` pointing to original |
| "+1 · 3" reaction | 3 rows in `reactions` table |
| Message appearing instantly | WebSocket + Redis Pub/Sub fan-out |

---

## 2. Why This Project?

### For learning

Most beginners build todo lists or blog APIs. Those teach routes and databases but nothing about:

- How to push data to clients without them asking (WebSockets)
- How to deliver one event to many recipients across server instances (Pub/Sub)
- How to track who is online without destroying your database (Redis TTL)
- How to process work asynchronously without blocking your API (background jobs)
- How to observe a running system in production (Prometheus + Grafana)

PulseChat forces you to learn all of these because the product literally does not work without them.

### For resume impact

At 2 years of experience, most developers have only built REST APIs with CRUD operations. Adding "I built a real-time WebSocket chat backend with Redis Pub/Sub fan-out and a presence system" to your resume puts you in the top 5% of backend candidates at that experience level.

---

## 3. Tech Stack — Every Tool Explained

### Python + FastAPI

FastAPI is the web framework that handles incoming requests (HTTP and WebSocket), routes them to the right function, validates input, and returns responses.

**Why FastAPI over Flask:** Flask has no native async support. FastAPI is async-first — crucial for WebSockets. It also auto-generates Swagger docs from type hints.

**Why FastAPI over Django:** Django is a full-stack framework with ORM, templating, admin panel — far more than needed for a pure API backend.

### PostgreSQL

The permanent relational database storing all business data — users, workspaces, channels, messages, reactions.

**Why PostgreSQL over MongoDB:** Chat data is deeply relational. Messages belong to channels, channels belong to workspaces, users have roles per workspace. PostgreSQL enforces this with foreign keys. MongoDB has no native JOINs — you'd assemble data manually in Python. PostgreSQL's built-in SEQUENCE for `seq_num` is also atomic and race-condition-proof — MongoDB has no equivalent.

**Why PostgreSQL over SQLite:** SQLite is a file — it breaks under concurrent writes. 1000 WebSocket connections writing simultaneously would corrupt data. PostgreSQL handles thousands of concurrent connections safely.

### Redis

An in-memory data store — roughly 100x faster than PostgreSQL for reads/writes. Used for four completely separate purposes:

| Purpose | What's stored | Why Redis |
|---|---|---|
| Presence | `presence:ws:user = "online"` with 60s TTL | TTL auto-expires — no cleanup job needed |
| Pub/Sub | Message broker between server instances | PostgreSQL has no multi-instance broadcast |
| Rate limiting | Request counts per user per minute | Atomic increment + TTL in one command |
| Cache | Recent messages per channel | Avoids hitting PostgreSQL on every load |

### SQLAlchemy (ORM)

Lets you define database tables as Python classes and write queries in Python instead of raw SQL. Handles connection pooling, SQL injection prevention, and migration management via Alembic.

### Alembic

Database migration system — like Git but for your database schema. Every schema change is a versioned file that runs once. New developers run `alembic upgrade head` and their database matches production instantly.

**Why Alembic instead of `create_all`:** `create_all` is fine for Day 1 but cannot safely evolve an existing database. Alembic generates `ALTER TABLE` statements that add columns without dropping existing data.

### Pydantic

Data validation library. Every piece of data entering the API is validated before your service code runs. Invalid data gets a 422 error with field-level detail automatically.

### JWT (JSON Web Tokens)

Stateless authentication. After login, the server issues a signed token. The client sends this token on every request. Any server instance can verify any token without coordination — critical for horizontal scaling.

### bcrypt (direct, not passlib)

Password hashing. bcrypt is deliberately slow (~100ms per hash) to prevent brute-force attacks. Never store plain passwords — ever.

**Note:** `passlib` is incompatible with `bcrypt 4.x`. Use `bcrypt` directly.

### ARQ (Async Redis Queue)

Background job queue. Push tasks onto the queue ("send email to user 7") — ARQ worker processes pick them up asynchronously. Keeps API response times fast.

### Prometheus + Grafana

Prometheus collects metrics (request count, latency, active WebSocket connections). Grafana displays live dashboards. Essential for production observability.

### Docker + Docker Compose

Docker packages your application into a portable container. Docker Compose runs multiple containers together locally — FastAPI, PostgreSQL, Redis, Prometheus, Grafana with one command.

### GCP Cloud Run

Serverless container platform. Push a Docker image, Cloud Run handles HTTPS, auto-scaling, and availability. Cloud SQL manages PostgreSQL, Memorystore manages Redis.

---

## 4. System Architecture — All 7 Layers

```
┌─────────────────────────────────────────────────────────┐
│              Layer 1: Client                            │
│         Browser / Mobile App / API Client               │
└────────────────┬──────────────────┬─────────────────────┘
                 │ HTTP REST        │ WebSocket
                 ▼                  ▼
┌───────────────────┐  ┌────────────────────────────────┐
│  Layer 2          │  │  Layer 2                       │
│  HTTP Transport   │  │  WebSocket Transport           │
│  (login, history) │  │  (messages, presence, typing)  │
└────────┬──────────┘  └────────────────┬───────────────┘
         │                              │
         ▼                              ▼
┌─────────────────────────────────────────────────────────┐
│              Layer 3: FastAPI Application               │
│    Routing · Middleware · JWT Auth · Rate Limiting      │
└──┬─────────────┬──────────────┬──────────────┬──────────┘
   │             │              │              │
   ▼             ▼              ▼              ▼
┌──────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐
│Layer4│  │ Layer 4  │  │ Layer 4  │  │   Layer 4    │
│ Auth │  │Workspace │  │ Message  │  │  Presence    │
│ Svc  │  │  Svc     │  │  Svc     │  │    Svc       │
└──┬───┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘
   │           │             │               │
   ▼           ▼             ▼               ▼
┌────────────────────┐  ┌────────────────────────────────┐
│     Layer 5a       │  │          Layer 5b              │
│    PostgreSQL      │  │            Redis               │
│  (permanent store) │  │  (presence, pubsub, cache)     │
└────────────────────┘  └──────────────┬─────────────────┘
                                        │
                         ┌──────────────┼──────────────┐
                         ▼              ▼              ▼
                  ┌────────────┐ ┌──────────┐ ┌────────────┐
                  │  Layer 6a  │ │ Layer 6b │ │  Layer 6c  │
                  │Connection  │ │ Pub/Sub  │ │    ARQ     │
                  │ Manager    │ │ Listener │ │  Workers   │
                  └────────────┘ └──────────┘ └────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│              Layer 7: Observability                     │
│     Prometheus · Grafana · Structured JSON Logging      │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│              Infrastructure                             │
│   Docker Compose (local) · GCP Cloud Run (production)  │
└─────────────────────────────────────────────────────────┘
```

### Why two transports (HTTP + WebSocket)?

HTTP is for request-response operations — logging in, fetching history, creating channels. WebSocket is for push-based real-time operations — incoming messages, typing indicators, presence changes.

Using only HTTP would require polling (wasteful — 1000 users polling every second = 1000 empty requests/second). Using only WebSocket for everything adds unnecessary complexity to simple CRUD operations.

---

## 5. Database Design

### PostgreSQL Tables

```sql
users (
  id              UUID PRIMARY KEY,
  email           VARCHAR(255) UNIQUE NOT NULL,   -- indexed for login queries
  display_name    VARCHAR(100) NOT NULL,
  avatar_url      TEXT,
  hashed_password VARCHAR(255) NOT NULL,           -- bcrypt hash, never plain
  is_active       BOOLEAN DEFAULT TRUE,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
)

workspaces (
  id          UUID PRIMARY KEY,
  name        VARCHAR(100) NOT NULL,
  slug        VARCHAR(50) UNIQUE NOT NULL,         -- URL-friendly identifier
  description TEXT,
  owner_id    UUID REFERENCES users(id) ON DELETE RESTRICT,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW()
)

workspace_members (
  workspace_id  UUID REFERENCES workspaces(id) ON DELETE CASCADE,
  user_id       UUID REFERENCES users(id) ON DELETE CASCADE,
  role          VARCHAR(20) DEFAULT 'MEMBER',      -- OWNER | ADMIN | MEMBER
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY   (workspace_id, user_id)
)

channels (
  id            UUID PRIMARY KEY,
  workspace_id  UUID REFERENCES workspaces(id) ON DELETE CASCADE,
  name          VARCHAR(80) NOT NULL,
  description   TEXT,
  is_private    BOOLEAN DEFAULT FALSE,
  is_archived   BOOLEAN DEFAULT FALSE,
  created_by    UUID REFERENCES users(id) ON DELETE SET NULL,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  updated_at    TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE        (workspace_id, name)
)

channel_members (
  channel_id  UUID REFERENCES channels(id) ON DELETE CASCADE,
  user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
  role        VARCHAR(20) DEFAULT 'MEMBER',        -- ADMIN | MEMBER
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (channel_id, user_id)
)

messages (
  id          UUID PRIMARY KEY,
  channel_id  UUID REFERENCES channels(id) ON DELETE CASCADE,
  sender_id   UUID REFERENCES users(id) ON DELETE SET NULL,  -- nullable: survives user deletion
  content     TEXT NOT NULL,
  seq_num     BIGINT NOT NULL,                     -- monotonically increasing per channel
  parent_id   UUID REFERENCES messages(id) ON DELETE SET NULL,  -- NULL = top-level
  is_edited   BOOLEAN DEFAULT FALSE,
  is_deleted  BOOLEAN DEFAULT FALSE,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW(),
  -- Composite index: fast channel message fetching
  INDEX ix_messages_channel_seq (channel_id, seq_num)
)

reactions (
  id          UUID PRIMARY KEY,
  message_id  UUID REFERENCES messages(id) ON DELETE CASCADE,
  user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
  emoji       VARCHAR(10) NOT NULL,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE      (message_id, user_id, emoji)        -- prevent duplicate reactions
)

read_receipts (
  channel_id          UUID REFERENCES channels(id) ON DELETE CASCADE,
  user_id             UUID REFERENCES users(id) ON DELETE CASCADE,
  last_read_message_id UUID REFERENCES messages(id) ON DELETE SET NULL,
  updated_at          TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY         (channel_id, user_id)
)
```

### Key Design Decisions

**Why UUID for IDs?**
UUIDs don't expose business information — integer IDs tell attackers how many users you have. UUIDs can also be generated client-side or in distributed systems without a central coordinator.

**Why `seq_num` on messages?**
Timestamps can collide and don't guarantee ordering under concurrent inserts. PostgreSQL sequences are atomic — `nextval()` is guaranteed unique even with 1000 concurrent calls. Clients use seq_num to detect gaps and request missed messages.

**Why `is_deleted` (soft delete)?**
Threads reference parent messages by `parent_id`. Hard-deleting a parent orphans its replies. Soft delete preserves referential integrity — deleted messages return as "This message was deleted."

**Why `sender_id` is nullable?**
If a user deletes their account, their messages should still exist (channel history makes sense without them). `ON DELETE SET NULL` handles this — the message survives, sender_id becomes NULL.

**Why `ondelete="SET NULL"` on `created_by` in channels?**
Same reason — the channel should survive if its creator leaves the workspace.

**Why `ondelete="CASCADE"` on workspace_members?**
If a workspace is deleted, all memberships should automatically delete too. Without CASCADE, PostgreSQL throws a foreign key violation.

**Why composite index `(channel_id, seq_num)`?**
Your most frequent query is "give me the last 50 messages in channel X ordered by seq_num." The composite index makes this a direct lookup instead of a full table scan. `channel_id` comes first because you always filter by channel before sorting.

### Enum Values — Important Note

SQLAlchemy's `SAEnum` stores the Python enum **name** (left side of `=`) not the **value** (right side). So define enums with matching uppercase values:

```python
class WorkspaceRole(str, enum.Enum):
    OWNER = "OWNER"    # stored as "OWNER" in PostgreSQL
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"

class ChannelRole(str, enum.Enum):
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"
```

---

## 6. The 4 Hard Engineering Problems

### Problem 1: Fan-out — one message to N users across M servers

When user A sends a message to a channel with 50 members, all 50 need it instantly — even if connected to different server instances.

**Solution — Redis Pub/Sub:**
```
Server 1 (users A, B)          Server 2 (users C, D)
    │                               │
    ├── subscribes channel:xyz ◄────┤
    │                               │
User A sends message               │
    ├── save to PostgreSQL          │
    ├── publish to Redis ───────────┤
    │                               │
    ├── receive from Redis          ├── receive from Redis
    ├── push to User B (local)      ├── push to User C (local)
                                    └── push to User D (local)
```

### Problem 2: Presence — who's online without killing your database

**Wrong solution:** Store `is_online = True` in PostgreSQL — massive write load, needs a cleanup job.

**Right solution — Redis TTL:**
- On connect: `SET presence:{ws_id}:{user_id} "online" EX 60`
- On heartbeat (every 30s): same command, resets TTL
- On disconnect: `DEL` key + publish offline event
- Browser crash: key expires after 60s automatically — zero cleanup logic

### Problem 3: ConnectionManager — tracking live WebSocket objects

FastAPI has no built-in WebSocket registry. When Redis Pub/Sub delivers a message, you need to find the right WebSocket object in memory.

```python
class ConnectionManager:
    def __init__(self):
        # user_id → list of WebSockets (same user, multiple tabs)
        self.active: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, user_id: str, ws: WebSocket):
        await ws.accept()
        self.active[user_id].append(ws)

    def disconnect(self, user_id: str, ws: WebSocket):
        self.active[user_id].remove(ws)
        if not self.active[user_id]:
            del self.active[user_id]

    async def send_to_user(self, user_id: str, data: dict):
        dead = []
        for ws in self.active.get(user_id, []):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(user_id, ws)

manager = ConnectionManager()  # singleton
```

**Why `list[WebSocket]` not a single WebSocket?** The same user can have multiple tabs open — each tab is a separate WebSocket connection.

### Problem 4: Message ordering

Network jitter means messages can arrive out of order.

**Solution — channel-scoped PostgreSQL sequences:**
```sql
CREATE SEQUENCE IF NOT EXISTS channel_seq_{channel_id} START 1;

INSERT INTO messages (channel_id, sender_id, content, seq_num)
VALUES ($1, $2, $3, nextval('channel_seq_{channel_id}'))
RETURNING id, seq_num, created_at;
```

`nextval()` is atomic — two concurrent inserts cannot get the same seq_num. Clients track the highest seq_num seen and detect gaps.

---

## 7. Project Folder Structure

```
pulsechat/
│
├── app/
│   ├── main.py                    # FastAPI app, startup/shutdown, middleware
│   │
│   ├── core/
│   │   ├── config.py              # Pydantic BaseSettings — all env vars
│   │   ├── security.py            # bcrypt hashing + JWT encode/decode
│   │   ├── dependencies.py        # get_current_user injectable dependency
│   │   └── middleware.py          # CORS, rate limiting, Prometheus
│   │
│   ├── api/
│   │   └── v1/
│   │       ├── __init__.py        # APIRouter with all sub-routers
│   │       ├── auth.py            # POST /register, /login, /refresh, GET /me
│   │       ├── workspaces.py      # Workspace CRUD + member management
│   │       ├── channels.py        # Channel CRUD + join/leave
│   │       ├── messages.py        # Message CRUD + reactions + search
│   │       └── websocket.py       # WS /ws — real-time entry point
│   │
│   ├── services/
│   │   ├── auth.py                # register, login, token logic
│   │   ├── workspace.py           # workspace + member business logic
│   │   ├── channel.py             # channel + membership business logic
│   │   ├── message.py             # message CRUD + pagination + reactions
│   │   └── presence.py            # heartbeat, presence read/write
│   │
│   ├── models/                    # SQLAlchemy ORM table definitions
│   │   ├── __init__.py            # imports all models (required for Alembic)
│   │   ├── base.py                # TimestampMixin (created_at, updated_at)
│   │   ├── user.py
│   │   ├── workspace.py           # Workspace + WorkspaceMember + WorkspaceRole
│   │   ├── channel.py             # Channel + ChannelMember + ChannelRole
│   │   └── message.py             # Message + Reaction
│   │
│   ├── schemas/                   # Pydantic request/response shapes
│   │   ├── auth.py                # RegisterRequest, LoginRequest, TokenResponse
│   │   ├── workspace.py           # WorkspaceCreate, InviteMemberRequest
│   │   ├── channel.py             # ChannelCreate, ChannelResponse
│   │   └── message.py             # SendMessageRequest, PaginatedMessagesResponse
│   │
│   ├── db/
│   │   ├── session.py             # Async SQLAlchemy engine + session factory + Base
│   │   └── redis.py               # Async Redis connection pool
│   │
│   ├── realtime/
│   │   ├── connection_manager.py  # ConnectionManager singleton
│   │   └── pubsub_listener.py     # Redis subscriber + fan-out logic
│   │
│   └── workers/
│       └── tasks.py               # ARQ background job definitions
│
├── alembic/                       # Database migrations
│   ├── versions/                  # One file per migration
│   └── env.py                     # Alembic async config
│
├── tests/
│   ├── conftest.py                # Fixtures — test DB, test client, mock Redis
│   ├── test_auth.py
│   ├── test_messages.py
│   └── test_websocket.py
│
├── docker-compose.yml             # PostgreSQL + Redis + Prometheus + Grafana
├── Dockerfile                     # Multi-stage production build
├── prometheus.yml                 # Prometheus scrape config
├── .env                           # Local secrets (never commit)
├── .env.example                   # Template for teammates
├── .gitignore
├── requirements.txt
└── alembic.ini
```

### Why this structure?

- `api/` — only HTTP concerns (status codes, request/response shapes)
- `services/` — only business logic (no HTTP concepts)
- `models/` — only database schema (no business logic)
- `schemas/` — only data shapes (no database concepts)
- `realtime/` — isolates WebSocket-specific components
- `workers/` — isolates async job definitions

---

## 8. Environment Setup

### Prerequisites

```bash
python3 --version      # need 3.11+
docker --version       # need 20+
docker compose version # need v2
git --version
```

### Installation

```bash
# Create project and virtual environment
mkdir pulsechat && cd pulsechat
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install fastapi==0.115.0 \
            "uvicorn[standard]==0.30.6" \
            sqlalchemy==2.0.35 \
            asyncpg==0.29.0 \
            alembic==1.13.3 \
            pydantic==2.9.2 \
            pydantic-settings==2.5.2 \
            python-jose==3.3.0 \
            bcrypt==4.2.0 \
            redis==5.1.0 \
            python-dotenv==1.0.1 \
            httpx==0.27.2

pip freeze > requirements.txt
```

### Environment Variables

```bash
# .env
DATABASE_URL=postgresql+asyncpg://pulsechat:pulsechat123@localhost:5432/pulsechat
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-super-secret-key-change-this-in-production-min-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
ENVIRONMENT=development
```

### Docker Compose

```yaml
# docker-compose.yml
services:
  db:
    image: postgres:16-alpine
    container_name: pulsechat_db
    environment:
      POSTGRES_USER: pulsechat
      POSTGRES_PASSWORD: pulsechat123
      POSTGRES_DB: pulsechat
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U pulsechat"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: pulsechat_redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  postgres_data:
  redis_data:
```

### Common Port Conflicts

If port 5432 or 6379 are already in use by system services:

```bash
# Check what's using the port
sudo lsof -i :5432
sudo lsof -i :6379

# Stop system services
sudo systemctl stop postgresql
sudo systemctl disable postgresql
sudo systemctl stop redis
sudo systemctl disable redis

# Restart Docker containers
docker compose down && docker compose up -d
```

### Start Everything

```bash
# Start infrastructure
docker compose up -d

# Verify healthy
docker compose ps

# Run database migrations
alembic upgrade head

# Start FastAPI server
uvicorn app.main:app --reload --port 8000

# Open API docs
# http://localhost:8000/docs
```

---

## 9. Day-by-Day Build Log

### Day 1 ✅ — Project Setup

**What was built:**
- Complete folder structure with all `__init__.py` files
- `app/core/config.py` — Pydantic BaseSettings reading from `.env`
- `app/db/session.py` — Async SQLAlchemy engine + connection pool + Base
- `app/db/redis.py` — Async Redis connection pool
- `app/main.py` — FastAPI app with lifespan, CORS, health check
- `docker-compose.yml` — PostgreSQL + Redis in Docker
- `Dockerfile` — Multi-stage production build
- `.env`, `.env.example`, `.gitignore`

**Key concepts learned:**
- Why virtual environments (isolated Python per project)
- Why Docker for databases (no system pollution, reproducible)
- Why `lifespan` over `@app.on_event` (modern FastAPI pattern)
- Why CORS middleware (browser security, different ports)
- Why Pydantic BaseSettings (type-validated config, clear errors on missing vars)

**Verify:**
```bash
curl http://localhost:8000/health
# {"status":"healthy","app":"PulseChat","version":"0.1.0"}
```

---

### Day 2 ✅ — Database Models + Alembic

**What was built:**
- `app/models/base.py` — TimestampMixin with `created_at`, `updated_at`
- `app/models/user.py` — User model
- `app/models/workspace.py` — Workspace + WorkspaceMember + WorkspaceRole enum
- `app/models/channel.py` — Channel + ChannelMember + ChannelRole enum
- `app/models/message.py` — Message + Reaction (with self-referential relationship)
- Alembic initialized and configured for async SQLAlchemy
- First migration generated and run — all 8 tables created

**Key concepts learned:**

**Alembic vs `create_all`:** Alembic tracks every schema change as a versioned file — like Git for your database. `create_all` only creates tables that don't exist, can't modify existing ones, and has no history. Every production backend uses migrations.

**Alembic commands:**
```bash
alembic revision --autogenerate -m "description"  # generate migration
alembic upgrade head                               # apply all pending
alembic downgrade -1                               # undo last migration
alembic history --verbose                          # see all migrations
```

**SQLAlchemy relationships:**
```python
# One-to-many: one channel has many messages
# Channel (one side) — list in type annotation
messages: Mapped[list["Message"]] = relationship(back_populates="channel")

# Message (many side) — no list in type annotation
channel: Mapped["Channel"] = relationship(back_populates="messages")

# back_populates always comes in pairs — strings must match attribute names exactly

# Self-referential (messages replying to messages)
replies: Mapped[list["Message"]] = relationship(
    "Message",
    foreign_keys="[Message.parent_id]",
    primaryjoin="Message.parent_id == Message.id",
    back_populates="parent",
)
```

**N+1 query problem — always use selectinload for lists:**
```python
# BAD — fires 50 separate queries (one per message) to load reactions
messages = await session.execute(select(Message).limit(50))

# GOOD — fires exactly 2 queries total
messages = await session.execute(
    select(Message)
    .limit(50)
    .options(selectinload(Message.reactions))  # ← one extra query for all reactions
)
```

**Verify:**
```bash
docker exec -it pulsechat_db psql -U pulsechat -d pulsechat -c "\dt"
# Should show all 8 tables
```

---

### Day 3 ✅ — Authentication

**What was built:**
- `app/core/security.py` — bcrypt hashing + JWT encode/decode (using bcrypt directly, not passlib)
- `app/schemas/auth.py` — RegisterRequest, LoginRequest, TokenResponse, UserResponse
- `app/services/auth.py` — register + login business logic
- `app/core/dependencies.py` — `get_current_user` injectable dependency
- `app/api/v1/auth.py` — 4 endpoints: register, login, refresh, /me

**Key concepts learned:**

**JWT flow:**
```
LOGIN:
  User sends email + password
  → Server verifies password with bcrypt.checkpw()
  → Server creates JWT: {"sub": "user_id", "exp": "30min", "type": "access"}
  → Server signs it with SECRET_KEY
  → Returns access_token (30min) + refresh_token (7 days)

EVERY REQUEST AFTER:
  User sends "Authorization: Bearer <token>"
  → get_current_user dependency runs
  → Decodes and verifies JWT signature
  → Reads user_id from "sub" claim
  → Loads user from database
  → Injects User object into route function
```

**Why two tokens?** If access_token is stolen, it expires in 30 minutes. Refresh_token never travels with every request — only used to get a new access_token.

**Why `passlib` was dropped:** `passlib` is unmaintained and incompatible with `bcrypt 4.x`. The error `module 'bcrypt' has no attribute '__about__'` confirms this. Solution: use bcrypt directly.

```python
# Direct bcrypt usage (no passlib)
import bcrypt

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())
```

**Why same error for wrong email AND wrong password?**
Security — separate messages let attackers enumerate which emails are registered. One generic message reveals nothing.

**Verify:**
```bash
# Register
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"vishal@gmail.com","display_name":"Vishal","password":"Sai@1010"}'

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"vishal@gmail.com","password":"Sai@1010"}'

# Protected route
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

### Day 4 ✅ — Workspaces + Channels

**What was built:**
- `app/schemas/workspace.py` — WorkspaceCreate, WorkspaceResponse, InviteMemberRequest
- `app/schemas/channel.py` — ChannelCreate, ChannelResponse, ChannelMemberResponse
- `app/services/workspace.py` — create, list, get, invite, list_members
- `app/services/channel.py` — create, list, get, join, leave
- `app/api/v1/workspaces.py` — 4 endpoints
- `app/api/v1/channels.py` — 5 endpoints

**Key concepts learned:**

**Three-layer protection on every endpoint:**
1. Authentication — are you logged in? (`get_current_user`)
2. Authorization — are you a member? (service checks workspace_members)
3. Permission — do you have the right role? (OWNER/ADMIN required for invite)

**Why `flush()` not `commit()` when creating workspace + membership:**
```python
session.add(workspace)
await session.flush()   # writes workspace, gets workspace.id back
                        # transaction still open

membership = WorkspaceMember(workspace_id=workspace.id, ...)
session.add(membership)
await session.flush()   # writes membership in same transaction

# If EITHER fails, BOTH roll back — atomicity guaranteed
# commit() happens in get_db() after the route succeeds
```

**Cursor-based pagination vs offset:**
```sql
-- WRONG: offset pagination — slow at scale, pages shift on new inserts
SELECT * FROM messages LIMIT 20 OFFSET 60

-- RIGHT: cursor pagination — always consistent, no full scan
SELECT * FROM messages
WHERE channel_id = $1 AND seq_num < 847  -- 847 is the cursor
ORDER BY seq_num DESC
LIMIT 20
```

**Bugs encountered and fixed:**

1. `list_workspaces` JOIN bug — `WorkspaceMember.workspace_id == user.id` should be `== Workspace.id`
2. WorkspaceRole enum stored as `"OWNER"` (uppercase name) not `"owner"` (lowercase value) — fixed by defining `OWNER = "OWNER"`
3. `model_config` written as string instead of dict — fixed by using `ConfigDict(from_attributes=True)`

---

### Day 5 ✅ — Messages REST API

**What was built:**
- `app/schemas/message.py` — SendMessageRequest, MessageResponse, PaginatedMessagesResponse
- `app/services/message.py` — send, get (paginated), edit, delete, add/remove reaction, search
- `app/api/v1/messages.py` — 7 endpoints

**Key concepts learned:**

**Cursor pagination implementation:**
```python
# Fetch limit+1 rows — the extra row tells you if there are more
query = select(Message).limit(limit + 1)

messages = list(result.scalars().all())
has_more = len(messages) > limit
if has_more:
    messages = messages[:limit]   # remove the extra row

messages.reverse()  # query DESC for cursor, return ASC for display
```

**Why `limit + 1`?** Avoids a separate COUNT query. If you get 51 rows when limit=50, there are more. If you get ≤50, you've reached the beginning.

**PostgreSQL sequence for seq_num:**
```python
seq_name = f"channel_seq_{str(channel_id).replace('-', '_')}"
await session.execute(text(f"CREATE SEQUENCE IF NOT EXISTS {seq_name} START 1"))
result = await session.execute(text(f"SELECT nextval('{seq_name}')"))
seq_num = result.scalar()
```

**Why not `MAX(seq_num) + 1`?** Race condition — two concurrent inserts both read the same MAX, both add 1, both try to insert the same seq_num. `nextval()` is atomic — guaranteed unique.

**Verify:**
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"vishal@gmail.com","password":"Sai@1010"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s -X POST http://localhost:8000/api/v1/channels/$CH_ID/messages \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content":"Hello PulseChat!"}' | python3 -m json.tool
```

---

## 10. API Reference

### Auth

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/auth/register` | None | Create account, get tokens |
| POST | `/api/v1/auth/login` | None | Login, get tokens |
| POST | `/api/v1/auth/refresh` | Refresh token | Get new access token |
| GET | `/api/v1/auth/me` | JWT | Get current user |

### Workspaces

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/workspaces` | JWT | Create workspace |
| GET | `/api/v1/workspaces` | JWT | List user's workspaces |
| GET | `/api/v1/workspaces/{id}` | JWT + member | Get workspace |
| POST | `/api/v1/workspaces/{id}/invite` | JWT + admin | Invite member |
| GET | `/api/v1/workspaces/{id}/members` | JWT + member | List members |

### Channels

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/workspaces/{id}/channels` | JWT + member | Create channel |
| GET | `/api/v1/workspaces/{id}/channels` | JWT + member | List channels |
| GET | `/api/v1/channels/{id}` | JWT + member | Get channel |
| POST | `/api/v1/channels/{id}/join` | JWT + member | Join public channel |
| DELETE | `/api/v1/channels/{id}/leave` | JWT + member | Leave channel |

### Messages

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/channels/{id}/messages` | JWT + member | Send message |
| GET | `/api/v1/channels/{id}/messages` | JWT + member | Paginated history |
| PATCH | `/api/v1/messages/{id}` | JWT + sender | Edit message |
| DELETE | `/api/v1/messages/{id}` | JWT + sender/admin | Soft delete |
| POST | `/api/v1/messages/{id}/reactions` | JWT + member | Add reaction |
| DELETE | `/api/v1/messages/{id}/reactions/{emoji}` | JWT + member | Remove reaction |
| GET | `/api/v1/channels/{id}/messages/search?q=` | JWT + member | Search messages |

### WebSocket (Day 6 — coming)

| Endpoint | Auth | Description |
|----------|------|-------------|
| `WS /ws?token={jwt}` | JWT via query param | Persistent real-time connection |

---

## 11. WebSocket Event Reference

### Client → Server

```jsonc
// Send a message
{"type":"message.send","channel_id":"uuid","content":"Hello","idempotency_key":"uuid"}

// Start typing
{"type":"typing.start","channel_id":"uuid"}

// Heartbeat (every 30s — keeps presence alive)
{"type":"heartbeat"}

// Mark messages as read
{"type":"read_receipt","channel_id":"uuid","message_id":"uuid"}
```

### Server → Client

```jsonc
// New message
{"type":"message.new","message":{"id":"uuid","content":"Hello","seq_num":47,...}}

// Typing indicator
{"type":"typing","channel_id":"uuid","user_id":"uuid","display_name":"Vishal"}

// Presence change
{"type":"presence.change","user_id":"uuid","status":"offline"}

// Reaction added
{"type":"reaction.add","message_id":"uuid","user_id":"uuid","emoji":"👍"}

// Error
{"type":"error","code":"rate_limited","message":"Too many messages"}
```

---

## 12. Redis Key Design

```
# Presence (auto-expires → auto-offline on disconnect or crash)
presence:{workspace_id}:{user_id}         → "online"      TTL: 60s

# Typing indicator (auto-expires → no "stop typing" event needed)
typing:{channel_id}:{user_id}             → "1"           TTL: 5s

# Rate limiting
ratelimit:msg:{user_id}                   → integer count  TTL: 60s
ratelimit:ws:{ip_address}                 → integer count  TTL: 60s

# Message cache
cache:messages:{channel_id}               → JSON string    TTL: 5m

# Idempotency (prevent duplicate sends on retry)
idempotency:{user_id}:{idempotency_key}   → message_id     TTL: 24h

# Pub/Sub topics (ephemeral — not stored, used for routing)
channel:{channel_id}                      → Pub/Sub topic
workspace:{workspace_id}                  → Pub/Sub topic (presence events)
```

---

## 13. Key Concepts Learned

| Concept | Where learned |
|---|---|
| Virtual environments | Day 1 setup |
| Docker + Docker Compose | Day 1 infrastructure |
| Pydantic Settings (config) | Day 1 `config.py` |
| Async SQLAlchemy | Day 2 session setup |
| SQLAlchemy relationships | Day 2 models |
| N+1 query problem + selectinload | Day 2 models |
| Alembic migrations | Day 2 |
| bcrypt password hashing | Day 3 |
| JWT tokens (access + refresh) | Day 3 |
| FastAPI dependency injection | Day 3 `get_current_user` |
| Service layer pattern | Day 3+ |
| Three-layer auth (authn + authz + permission) | Day 4 |
| `flush()` vs `commit()` | Day 4 |
| Cursor-based pagination | Day 5 |
| PostgreSQL sequences | Day 5 |
| Soft deletes | Day 5 |
| `selectinload` for reactions | Day 5 |
| Enum name vs value in SQLAlchemy | Day 4 bug fix |

---

## 14. Common Errors & Fixes

### Port already in use (5432 or 6379)

```bash
sudo systemctl stop postgresql   # for port 5432
sudo systemctl stop redis        # for port 6379
sudo systemctl disable postgresql
sudo systemctl disable redis
docker compose down && docker compose up -d
```

### `passlib` incompatible with `bcrypt 4.x`

```
Error: module 'bcrypt' has no attribute '__about__'
```

```bash
pip uninstall passlib -y
# Use bcrypt directly in security.py
```

### SQLAlchemy relationship error

```
ArgumentError: relationship 'sent_messages' expects a class or mapper
```

Fix: add `from __future__ import annotations` as line 1 in all model files. Pass class name as string to `relationship("ClassName", ...)`.

### `model_config` Pydantic error

```
ValueError: dictionary update sequence element #0 has length 15
```

Fix: use `ConfigDict` instead of dict syntax:

```python
from pydantic import ConfigDict

class MyModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # correct
    # NOT: model_config = {"from_attributes": True},  # trailing comma = tuple
```

### Empty list from `list_workspaces`

Wrong JOIN condition — comparing `workspace_id` to `user.id` instead of `Workspace.id`:

```python
# WRONG
.join(WorkspaceMember, WorkspaceMember.workspace_id == user.id)

# CORRECT
.join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
```

### WorkspaceRole enum mismatch

SQLAlchemy stores enum by name (uppercase) not value. Define:

```python
class WorkspaceRole(str, enum.Enum):
    OWNER = "OWNER"    # both sides uppercase
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"
```

### Docker `version` warning

Remove `version: "3.9"` from top of `docker-compose.yml` — it's obsolete.

---

## 15. Remaining Build Plan

```
Day 6  ⏳  WebSocket layer
           — ConnectionManager singleton
           — WS endpoint with JWT auth via query param
           — Client event handling (message.send, heartbeat, typing)
           — Server event broadcasting

Day 7  ⏳  Redis Pub/Sub fan-out
           — pubsub_listener.py background task
           — Subscribe to all active channel topics on startup
           — Fan-out incoming messages to locally connected users
           — Multi-server delivery architecture

Day 8  ⏳  Presence system
           — Online/offline/away status
           — Heartbeat every 30s resets 60s TTL
           — Typing indicator with 5s TTL auto-expire
           — Publish presence changes to workspace members

Day 9  ⏳  Background jobs (ARQ)
           — Email notifications for offline members
           — PDF channel history export
           — Scheduled daily summary emails

Day 10 ⏳  Monitoring
           — Prometheus middleware (request count, latency, WS connections)
           — Custom metrics (messages/sec, fan-out latency)
           — Grafana dashboard setup
           — Structured JSON logging

Day 11 ⏳  Testing
           — pytest + async fixtures
           — TestClient for HTTP endpoints
           — WebSocket simulation tests
           — Mock Redis for unit tests
           — Target 80%+ coverage

Day 12 ⏳  Deployment
           — Multi-stage Dockerfile
           — GCP Cloud Run configuration
           — Cloud SQL + Memorystore setup
           — GitHub Actions CI/CD pipeline
```

---

## 16. Resume Bullet Points

```
• Built a production-ready real-time chat API serving persistent WebSocket
  connections with Redis Pub/Sub fan-out across horizontally-scaled FastAPI instances

• Implemented a TTL-based user presence system using Redis with sub-second
  online/offline propagation to all connected workspace members

• Designed a multi-tenant workspace architecture with channel-scoped message
  ordering using PostgreSQL sequences for gap-detectable delivery guarantees

• Engineered a ConnectionManager registry handling concurrent WebSocket connections
  per user with graceful stale-connection cleanup and multi-tab support

• Built Redis-backed rate limiting and idempotency key validation to prevent
  message duplication under network retry conditions

• Implemented cursor-based pagination for message history, full-text search,
  soft deletes, thread replies, and emoji reactions with optimistic concurrency

• Instrumented the API with Prometheus tracking active WebSocket connections,
  message throughput, and p95 latency, visualised in live Grafana dashboards

• Deployed on GCP Cloud Run with Cloud SQL and Memorystore via Docker
  multi-stage builds and GitHub Actions CI/CD pipeline
```

---

## 17. Interview Questions This Project Unlocks

### WebSocket & real-time

- How would you scale to 100,000 concurrent WebSocket connections?
- What happens to a message if the client disconnects mid-send?
- How do you authenticate a WebSocket connection? (Can't use HTTP headers easily)
- What's the difference between WebSocket and Server-Sent Events?

### Redis & distributed systems

- What happens to messages if the Redis Pub/Sub broker goes down?
- How do you prevent a race condition when two users send messages simultaneously?
- Why use Redis TTL for presence instead of a database `is_online` column?
- What is the difference between Redis Pub/Sub and Redis Streams?

### Database design

- Why do you use `seq_num` instead of `created_at` for message ordering?
- What is cursor-based pagination and why is it better than offset at scale?
- How do you handle a user deleting a message that has thread replies?
- How would you implement unread message counts efficiently?

### Architecture

- What is the service layer pattern and why separate it from routes?
- How would you add end-to-end encryption to messages?
- How would you implement push notifications for mobile clients?
- How would you handle a workspace with 10,000 members in one channel?

---

*README version 1.0 — covers Days 1–5 (backend REST complete). Days 6–12 (WebSocket, Redis Pub/Sub, presence, jobs, monitoring, testing, deployment) in progress.*
