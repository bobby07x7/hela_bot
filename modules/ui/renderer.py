"""
Live-editable UI system.

Every user-facing string has a `key` (e.g. "welcome", "economy.balance").
Defaults ship in /locales/<locale>.json. An owner can override any key at
runtime with `/editui <key> <new text>`, which writes to the `ui_messages`
table. `render()` always checks the DB override first, falling back to the
locale file, so changes apply instantly with no restart.

A small in-process cache avoids hitting the DB on every message; `reload_ui()`
clears it and is called automatically whenever /editui writes a change.
"""
from __future__ import annotations

import json
from pathlib import Path

from core.config import get_settings

_LOCALES_DIR = Path(__file__).resolve().parent.parent.parent / "locales"
_locale_cache: dict[str, dict] = {}
_override_cache: dict[str, str] | None = None


def _load_locale(locale: str) -> dict:
    if locale not in _locale_cache:
        path = _LOCALES_DIR / f"{locale}.json"
        if not path.exists():
            path = _LOCALES_DIR / "en.json"
        _locale_cache[locale] = json.loads(path.read_text(encoding="utf-8"))
    return _locale_cache[locale]


async def _load_overrides() -> dict[str, str]:
    global _override_cache
    if _override_cache is not None:
        return _override_cache

    # Imported lazily to avoid a circular import with core.permissions.
    from database.models import UIMessage
    from database.session import get_session
    from sqlalchemy import select

    overrides: dict[str, str] = {}
    try:
        async with get_session() as session:
            result = await session.execute(select(UIMessage))
            for row in result.scalars():
                overrides[row.key] = row.content
    except Exception:
        # DB not reachable yet (e.g. first boot before init_models) -
        # fall back to locale defaults only.
        overrides = {}
    _override_cache = overrides
    return overrides


def reload_ui() -> None:
    """Invalidate the override cache; call after any /editui write."""
    global _override_cache
    _override_cache = None


async def render(key: str, locale: str | None = None, **kwargs) -> str:
    """Resolve `key` to display text, DB override first then locale default,
    and format it with kwargs (missing placeholders are left untouched)."""
    settings = get_settings()
    locale = locale or settings.default_locale

    overrides = await _load_overrides()
    template = overrides.get(key)

    if template is None:
        defaults = _load_locale(locale)
        template = defaults.get(key, key)

    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template
