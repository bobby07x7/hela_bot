from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import FilterWord


def message_contains_filtered_word(text: str, words: list[str]) -> str | None:
    """Pure: case-insensitive whole-word-ish substring check. Returns the
    first matching word, or None. Deliberately simple (substring, not full
    tokenization) so it also catches leetspeak-adjacent variants a strict
    word-boundary regex would miss, at the cost of some false positives on
    short filter words - group admins should pick specific enough words."""
    lowered = text.lower()
    for word in words:
        if word.lower() in lowered:
            return word
    return None


async def get_filtered_words(session: AsyncSession, chat_id: int) -> list[str]:
    result = await session.execute(select(FilterWord).where(FilterWord.chat_id == chat_id))
    return [row.word for row in result.scalars()]


async def add_word(session: AsyncSession, chat_id: int, word: str, added_by: int) -> bool:
    """Returns False if the word was already filtered."""
    existing = await get_filtered_words(session, chat_id)
    if word.lower() in [w.lower() for w in existing]:
        return False
    session.add(FilterWord(chat_id=chat_id, word=word, added_by=added_by))
    await session.flush()
    return True


async def remove_word(session: AsyncSession, chat_id: int, word: str) -> bool:
    result = await session.execute(select(FilterWord).where(FilterWord.chat_id == chat_id))
    rows = list(result.scalars())
    target = next((r for r in rows if r.word.lower() == word.lower()), None)
    if target is None:
        return False
    await session.delete(target)
    return True
