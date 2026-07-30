# Hela Bot

A modular, production-oriented Telegram bot skeleton: async Python,
PostgreSQL + Redis, a live-editable UI system, an 11-tier permission model,
economy/moderation/support modules, Docker Compose deployment, and a
starter FastAPI dashboard.

## Honest scope note

The original spec called for 320+ commands and an enormous feature set
(RPG, pets, guilds, market, AI moderation, full web dashboard with 2FA,
themes, image generation, GitHub/Railway automation, etc.). Building all
of that at production quality in one pass isn't realistic — a lot of that
list is easily 10,000+ lines of real, tested code and weeks of work.

What this repo gives you instead is **the real architecture**, fully
wired end-to-end with working commands in every planned category, so you
(or an AI pair-programmer) can extend it module-by-module without
re-doing the foundation:

| Category | Implemented now | How to extend |
|---|---|---|
| Core / permissions | 11-level enum, decorator-based middleware, group-admin live check | `core/permissions.py` |
| Economy | `/balance /daily /work /pay /leaderboard` | add functions to `modules/economy/service.py`, commands to `modules/economy/commands.py` |
| Moderation | `/warn /mute /kick /ban` | `modules/moderation/commands.py` |
| Bot-admin | `/addcoins /removecoins /resetuser` | `modules/admin/commands.py` |
| Owner | `/broadcast /maintenance /stats` | `modules/owner/commands.py` |
| Support | `/ticket /tickets /reply /close` | `modules/support/commands.py` |
| Live UI editor | `/editui <key> <text>`, `/ui <key>` preview, DB-backed with in-process cache, zero restart | `modules/ui/` |
| Logging | `AuditLog` + `BroadcastLog` tables, structured stdout logging | `core/logging.py`, `database/models.py` |
| Scheduler | APScheduler wired in `main.py`, one job (premium expiry) | `scheduler/jobs.py` |
| Dashboard | FastAPI app with `/health` and `/stats` | `dashboard/api/main.py` |
| Deployment | Dockerfile + docker-compose (bot, postgres, redis, api) | as-is |
| Migrations | Alembic wired to the async engine, no versions generated yet | `alembic revision --autogenerate` |

Modules you asked for that are **not** built (RPG/pets/guilds/market,
force-join, captcha, themes, image cards, AI features, GitHub/Railway
automation, JWT/2FA dashboard auth) are intentionally left out rather than
faked — the architecture is exactly the same shape as what exists, so
adding e.g. `modules/rpg/` or `modules/guild/` follows the identical
pattern as `modules/economy/`.

## Architecture

```
hela_bot/
  core/            # config, permissions, logging, cache, bot wiring, /start /help
  database/        # SQLAlchemy models + async session
  modules/
    economy/       # service.py (logic) + commands.py (handlers)
    moderation/
    admin/
    owner/
    support/
    ui/            # renderer.py (locale + DB overrides) + editor.py (/editui)
  scheduler/       # APScheduler jobs
  locales/         # en.json - every UI string, keyed
  dashboard/api/   # FastAPI starter
  alembic/         # migrations
  tests/           # pytest + pytest-asyncio, sqlite-backed unit tests
```

Each module follows the same split: **service** (pure business logic,
easy to unit test) and **commands** (thin Telegram handlers that call the
service and render UI strings). Every command that needs a permission
level wraps with `@require_permission(PermissionLevel.X)`.

### Permission levels

```
GUEST < USER < PREMIUM < VIP < MODERATOR < GROUP_ADMIN < GROUP_OWNER
< SUPPORT_STAFF < DEVELOPER < BOT_ADMIN < SUPER_ADMIN < BOT_OWNER
```

`BOT_OWNER` / `DEVELOPER` / `SUPPORT_STAFF` come from `OWNER_IDS` /
`DEVELOPER_IDS` / `SUPPORT_STAFF_IDS` in `.env`. `GROUP_ADMIN` /
`GROUP_OWNER` are resolved live via the Telegram API per-chat. Everything
else (`PREMIUM`, `VIP`, `MODERATOR`, `BOT_ADMIN`, `SUPER_ADMIN`) is a
column on the `users` table you can set manually or via a future
`/promote` command.

### Live UI editing

Every user-facing string lives in `locales/en.json` under a key (e.g.
`"economy.balance"`). An owner can override any key at runtime:

```
/editui welcome Hey {first_name}, glad you're back!
```

This writes to the `ui_messages` table and invalidates the in-process
cache — the new text is live on the very next message, no restart, no
redeploy.

## Setup

### 1. Local (Python directly)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in BOT_TOKEN and OWNER_IDS at minimum
# either run against a local Postgres + Redis, or point DATABASE_URL at
# sqlite for a quick smoke test: sqlite+aiosqlite:///./hela.db
python main.py
```

### 2. Docker Compose (recommended)

```bash
cp .env.example .env   # fill in BOT_TOKEN and OWNER_IDS
docker compose up --build
```

This starts Postgres, Redis, the bot, and the dashboard API
(`http://localhost:8080/health`, `/stats`).

### 3. Migrations

```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

(`main.py` also calls `Base.metadata.create_all` on boot as a dev
convenience, so the bot works without Alembic for local testing — but
use migrations for anything you deploy for real.)

## Tests

```bash
pip install pytest pytest-asyncio aiosqlite
pytest
```

Tests run against an in-memory SQLite DB, so no external services are
needed.

## Adding a new module (e.g. RPG)

1. `mkdir modules/rpg && touch modules/rpg/__init__.py`
2. `modules/rpg/service.py` — pure functions taking an `AsyncSession` and
   returning data, following `modules/economy/service.py`.
3. `modules/rpg/commands.py` — thin handlers using
   `@require_permission(...)`, calling the service, rendering UI strings
   via `modules.ui.renderer.render(...)`.
4. Add any new tables to `database/models.py`.
5. Add UI strings to `locales/en.json` under an `"rpg.*"` namespace.
6. Register the new `CommandHandler`s in `core/bot.py`.
7. Add unit tests in `tests/test_rpg_service.py`.

Every other planned module (pets, guilds, market, premium, events,
force-join, themes, AI features) follows this exact same seven-step
pattern.
