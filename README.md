# Hela Bot

A modular, production-oriented Telegram bot: async Python, PostgreSQL +
Redis, an 11-tier permission model, a live-editable UI system, and **71
working commands** across economy, RPG, shop, pets, guilds, gambling,
premium, moderation, admin, owner, support, and force-join.

## If you're redeploying after a crash

Your previous deploy log showed:

```
TypeError: connect() got an unexpected keyword argument 'channel_binding'
```

That happened because Neon (and Railway/Heroku/Supabase's Postgres
plugins) hand you a `DATABASE_URL` like:

```
postgresql://user:pass@host/db?sslmode=require&channel_binding=require
```

...but this bot's async DB driver (`asyncpg`) doesn't understand
`sslmode` or `channel_binding` as connection keyword arguments - it wants
`postgresql+asyncpg://` as the scheme and `ssl=true` instead.

**This is now fixed at the code level.** `core/config.py` has a
`normalize_database_url()` function that automatically rewrites whatever
Postgres URL you paste into `DATABASE_URL` into the correct form at
startup - `postgres://` or `postgresql://` become `postgresql+asyncpg://`,
`sslmode=require` becomes `ssl=true`, and `channel_binding` is stripped.
You can paste your Neon URL in exactly as Neon gives it to you.

`main.py` also now runs a **preflight check** before starting the bot: it
tries to actually connect to Postgres and Redis first and logs a clear,
specific error (not a bare stack trace) if either one fails, so a bad
`DATABASE_URL`/`REDIS_URL` shows up immediately in the logs with an
actionable message instead of `/start` just silently doing nothing.

**One more thing, unrelated to the crash:** in an earlier message you
pasted your live `BOT_TOKEN`, Neon password, and Redis password into this
chat. If you haven't already, rotate all three (BotFather `/token`, Neon
dashboard, Redis Cloud dashboard) before putting the new values into
Railway - what was pasted here should be treated as compromised.

## Honest scope note - what "add all commands" means here

The original spec asked for 320+ commands and things like AI moderation,
a themed image-card system, GitHub/Railway deploy automation, and a full
2FA web dashboard. Faking that at production quality isn't something I'll
do - instead, every command in this repo is **real, wired into the bot,
and does what it says**: it hits the database, changes state, and returns
a real Telegram reply. Nothing here is a stub that just prints "coming
soon".

I got to 71 commands across every category from the spec (economy, RPG,
shop, pets, guilds, gambling, premium, moderation, admin, owner, support,
force-join, live UI editing) - not 320, because the remaining ~250 in the
original ask are mostly small variations on these same patterns (more
shop items, more RPG encounter types, more admin toggles) rather than new
architecture. Adding more is now mechanical: follow the same
service.py + commands.py pattern documented below.

### What I could and couldn't verify in my sandbox

I don't have network access in the environment I build in, so I can't
`pip install` SQLAlchemy/python-telegram-bot/etc. or run a live bot
against Telegram here. What I *did* do, for real, in this conversation:

- **Byte-compiled all 61 Python files** (`python -m py_compile`) - catches
  syntax errors.
- **Statically verified all 71 command handlers** referenced in
  `core/bot.py` resolve to real functions that exist in their modules
  (not typos/missing imports).
- **Statically verified all 114 UI-string keys** used in code exist in
  `locales/en.json`.
- **Actually executed the pure business logic** (no DB required) for
  every module's math: cooldown formatting, XP/leveling, RPG combat win
  rates (ran 2000-6000 trials and confirmed the win-rate curve matches
  the strength ratio), gambling payouts (coinflip/dice/slots, verified
  every payout branch over thousands of spins), pet hunger decay over
  time, shop catalog lookups, and force-join channel list add/remove.
  These all passed.
- **Wrote a full pytest suite** (`tests/`) covering every service module
  end-to-end against an in-memory SQLite DB - deposit/withdraw, leveling,
  fight coin-conservation, guild create/join/leave/kick permissions,
  lottery ticket pooling and payout, pet adoption, shop buy/sell/use. I
  could not execute these myself (no SQLAlchemy available in my sandbox),
  but they follow the exact same patterns as the pure-logic tests I did
  run, and you can verify them yourself in under a minute:
  ```bash
  pip install -r requirements.txt
  pytest
  ```
  If anything fails, paste me the output and I'll fix it.

What I have **not** verified: an actual live conversation with a real
Telegram bot token against Telegram's servers (needs your token + a
reachable network), and a real Postgres/Redis connection (needs your
credentials). The preflight check in `main.py` is designed specifically
to surface any problem there clearly in your deploy logs.

## Full command list (71)

**Economy** - `/balance` `/daily` `/work` `/pay` `/deposit` `/withdraw`
`/profile` `/rank` `/leaderboard`

**RPG** - `/adventure` `/hunt` `/fight` `/inventory`

**Shop** - `/shop` `/buy` `/sell` `/use`

**Pets** - `/adopt` `/pets` `/feed` `/releasepet`

**Guild** - `/guildcreate` `/guildjoin` `/guildleave` `/guildinfo`
`/guildlist` `/guilddonate` `/guildkick`

**Gambling** - `/coinflip` `/dice` `/slots` `/lotterybuy` `/lottery`
`/lotterydraw` (owner)

**Premium** - `/premium` `/grantpremium` (admin) `/revokepremium` (admin)

**Moderation** (group-admin+) - `/warn` `/unwarn` `/warnings` `/mute`
`/unmute` `/kick` `/ban` `/unban` `/purge`

**Force-join config** (group-admin+) - `/addforcejoin` `/removeforcejoin`
`/forcejoinlist`

**Bot-admin** - `/addcoins` `/removecoins` `/resetuser` `/promote`
`/demote` `/blacklist` `/unblacklist` `/groupban` `/groupunban`

**Owner** - `/broadcast` `/maintenance` `/stats` `/shutdown` `/editui`
`/ui` `/reloadui`

**Support** - `/ticket` `/tickets` (staff) `/reply` (staff) `/close`

**Core** - `/start` `/help`

## Architecture

```
hela_bot/
  core/            # config (incl. DB URL normalization), permissions, logging,
                    # cache, bot wiring, /start /help /common handlers
  database/        # SQLAlchemy models + async session + connectivity check
  modules/
    economy/       # service.py (logic) + commands.py (handlers)
    rpg/           # adventure/hunt/fight
    shop/          # buy/sell/use, static catalog
    pets/          # adopt/feed with time-based hunger decay
    guild/         # create/join/leave/donate/kick
    gambling/      # coinflip/dice/slots (pure) + lottery (DB-backed)
    premium/       # status + owner grant/revoke
    moderation/
    admin/
    owner/
    support/
    forcejoin/      # per-group mandatory-join channels + require_joined decorator
    ui/            # renderer.py (locale + DB overrides) + editor.py (/editui)
  scheduler/       # APScheduler jobs (premium expiry sweep)
  locales/         # en.json - all 123 UI strings, keyed
  dashboard/api/   # FastAPI starter (health + stats)
  alembic/         # migrations
  tests/           # pytest + pytest-asyncio, sqlite-backed unit tests
```

Each module follows the same split: **service** (pure or DB-touching
business logic, unit-testable without Telegram) and **commands** (thin
handlers that call the service and render UI strings). Every command that
needs a permission level wraps with `@require_permission(PermissionLevel.X)`.

### Permission levels

```
GUEST < USER < PREMIUM < VIP < MODERATOR < GROUP_ADMIN < GROUP_OWNER
< SUPPORT_STAFF < DEVELOPER < BOT_ADMIN < SUPER_ADMIN < BOT_OWNER
```

`BOT_OWNER` / `DEVELOPER` / `SUPPORT_STAFF` come from `OWNER_IDS` /
`DEVELOPER_IDS` / `SUPPORT_STAFF_IDS` in `.env`. `GROUP_ADMIN` /
`GROUP_OWNER` are resolved live via the Telegram API per-chat.
`PREMIUM`/`VIP`/`MODERATOR`/`BOT_ADMIN`/`SUPER_ADMIN` are a column on the
`users` table, settable via `/promote` (super-admin+).

### Live UI editing

Every user-facing string lives in `locales/en.json` under a key. An owner
can override any key at runtime:

```
/editui welcome Hey {first_name}, glad you're back!
```

Writes to the `ui_messages` table and invalidates the in-process cache -
live on the next message, no restart.

### Force-join

`/addforcejoin @channel` (group-admin+) makes a channel mandatory to use
the bot in that group. The `require_joined` decorator in
`modules/forcejoin/commands.py` is wired onto `/daily` as a working
example - stack it under `@require_permission` on any other command to
gate it the same way.

## Setup

### 1. Docker Compose (recommended)

```bash
cp .env.example .env   # fill in BOT_TOKEN, OWNER_IDS, DATABASE_URL, REDIS_URL
docker compose up --build
```

Starts Postgres, Redis, the bot, and the dashboard API
(`http://localhost:8080/health`, `/stats`).

### 2. Local Python

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python main.py
```

Watch the startup logs - the preflight check will tell you immediately
if `DATABASE_URL` or `REDIS_URL` can't be reached, with the actual reason.

### 3. Migrations

```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

(`main.py` also calls `Base.metadata.create_all` on boot as a dev
convenience, so it works without Alembic too - but use migrations for
anything you deploy for real.)

## Tests

```bash
pip install -r requirements.txt
pytest
```

Runs against an in-memory SQLite DB - no external services needed. Covers
every service module: economy, RPG, shop, pets, guild, gambling.

## Adding a new module

1. `mkdir modules/newthing && touch modules/newthing/__init__.py`
2. `modules/newthing/service.py` - functions taking an `AsyncSession`,
   following `modules/economy/service.py`. Extract pure/deterministic
   logic (math, odds, formatting) into standalone functions with no DB
   argument where possible - it's much easier to test and reason about.
3. `modules/newthing/commands.py` - thin handlers with
   `@require_permission(...)`, calling the service, rendering via
   `modules.ui.renderer.render(...)`.
4. Add any new tables to `database/models.py`.
5. Add UI strings to `locales/en.json` under a `"newthing.*"` namespace.
6. Register the `CommandHandler`s in `core/bot.py`.
7. Add `tests/test_newthing_service.py`.

Every module in this repo follows that exact seven-step pattern.
