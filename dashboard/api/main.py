"""
Starting point for the web dashboard's API layer.

Only read-only, JWT-free endpoints are wired up here (health + basic
stats) so the container boots cleanly out of the box. Auth (JWT/OAuth/2FA),
the UI editor endpoints, log streaming, and the React/Vue frontend are the
natural next slice to build on top of this - see README.md "Extending the
dashboard".
"""
from __future__ import annotations

from fastapi import FastAPI
from sqlalchemy import func, select

from core.config import get_settings
from database.models import GroupChat, Ticket, TicketStatus, User
from database.session import get_session

app = FastAPI(title="Hela Bot Dashboard API", version="0.1.0")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/stats")
async def stats() -> dict:
    async with get_session() as session:
        users = (await session.execute(select(func.count()).select_from(User))).scalar_one()
        groups = (await session.execute(select(func.count()).select_from(GroupChat))).scalar_one()
        open_tickets = (
            await session.execute(select(func.count()).select_from(Ticket).where(Ticket.status == TicketStatus.OPEN))
        ).scalar_one()

    return {"users": users, "groups": groups, "open_tickets": open_tickets}


def run() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(app, host="0.0.0.0", port=settings.api_port)


if __name__ == "__main__":
    run()
