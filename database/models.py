from __future__ import annotations

import datetime as dt
import enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class PermissionLevel(enum.IntEnum):
    """Mirrors core.permissions.PermissionLevel; kept separate so the DB
    layer never imports python-telegram-bot code."""

    GUEST = 0
    USER = 1
    PREMIUM = 2
    VIP = 3
    MODERATOR = 4
    GROUP_ADMIN = 5
    GROUP_OWNER = 6
    SUPPORT_STAFF = 7
    DEVELOPER = 8
    BOT_ADMIN = 9
    SUPER_ADMIN = 10
    BOT_OWNER = 11


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    balance: Mapped[int] = mapped_column(Integer, default=0)
    bank: Mapped[int] = mapped_column(Integer, default=0)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[int] = mapped_column(Integer, default=1)

    daily_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_daily_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_work_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    permission_level: Mapped[int] = mapped_column(Integer, default=int(PermissionLevel.USER))
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    premium_until: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    ban_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)

    locale: Mapped[str] = mapped_column(String(8), default="en")

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    warnings: Mapped[list["Warning"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class GroupChat(Base):
    __tablename__ = "group_chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)

    force_join_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    force_join_channels: Mapped[list] = mapped_column(JSON, default=list)

    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Warning(Base):
    __tablename__ = "warnings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(String(512))
    issued_by: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(back_populates="warnings")


class TicketStatus(str, enum.Enum):
    OPEN = "open"
    PENDING = "pending"
    CLOSED = "closed"


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    subject: Mapped[str] = mapped_column(String(256))
    status: Mapped[TicketStatus] = mapped_column(Enum(TicketStatus), default=TicketStatus.OPEN)
    priority: Mapped[str] = mapped_column(String(16), default="normal")
    assigned_to: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    closed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    messages: Mapped[list["TicketMessage"]] = relationship(back_populates="ticket", cascade="all, delete-orphan")


class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"))
    sender_id: Mapped[int] = mapped_column(BigInteger)
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    ticket: Mapped["Ticket"] = relationship(back_populates="messages")


class UIMessage(Base):
    """Backing store for the live /editui system - every editable UI
    surface (welcome text, error text, buttons...) is a row here."""

    __tablename__ = "ui_messages"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    content: Mapped[str] = mapped_column(Text)
    buttons: Mapped[list] = mapped_column(JSON, default=list)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(64))
    target: Mapped[str | None] = mapped_column(String(128), nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BroadcastLog(Base):
    __tablename__ = "broadcast_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sent_by: Mapped[int] = mapped_column(BigInteger)
    total: Mapped[int] = mapped_column(Integer, default=0)
    success: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
