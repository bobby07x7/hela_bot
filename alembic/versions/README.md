# Alembic migration versions

This folder is intentionally empty in the starter repo. Generate your first
migration once you have a real Postgres instance to connect to:

```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

`main.py` also calls `init_models()` on boot as a dev convenience (creates
any missing tables via `Base.metadata.create_all`), so the bot will run
without migrations too - but for anything beyond local dev, use Alembic so
schema changes are tracked and reversible.
