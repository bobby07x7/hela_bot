from __future__ import annotations

import pytest

from modules.themes import service

pytestmark = pytest.mark.asyncio


def test_apply_theme_header_wraps_with_border():
    assert service.apply_theme_header("minimal", "Leaderboard") == "- Leaderboard -"
    assert service.apply_theme_header("neon", "X").startswith("\U0001F49C")


def test_invalid_theme_falls_back_to_default():
    assert service.apply_theme_header("not_a_real_theme", "X") == service.apply_theme_header("default", "X")


async def test_get_group_theme_defaults_when_unset(session):
    theme = await service.get_group_theme(session, chat_id=800)
    assert theme == service.DEFAULT_THEME


async def test_set_and_get_group_theme(session):
    ok = await service.set_group_theme(session, chat_id=801, title="Test Group", theme_name="neon")
    assert ok is True
    theme = await service.get_group_theme(session, chat_id=801)
    assert theme == "neon"


async def test_set_invalid_theme_fails(session):
    ok = await service.set_group_theme(session, chat_id=802, title="Test Group", theme_name="bogus")
    assert ok is False
