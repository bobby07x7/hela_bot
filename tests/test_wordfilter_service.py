from __future__ import annotations

import pytest

from modules.wordfilter import service

pytestmark = pytest.mark.asyncio


def test_message_contains_filtered_word_matches_case_insensitively():
    assert service.message_contains_filtered_word("this has a BadWord here", ["badword"]) == "badword"
    assert service.message_contains_filtered_word("totally clean", ["badword"]) is None


async def test_add_word_then_duplicate_add_fails(session):
    added = await service.add_word(session, chat_id=700, word="spam", added_by=1)
    assert added is True
    duplicate = await service.add_word(session, chat_id=700, word="SPAM", added_by=1)
    assert duplicate is False  # case-insensitive dedupe


async def test_remove_word(session):
    await service.add_word(session, chat_id=701, word="scam", added_by=1)
    removed = await service.remove_word(session, chat_id=701, word="scam")
    assert removed is True
    words = await service.get_filtered_words(session, 701)
    assert words == []


async def test_remove_nonexistent_word_returns_false(session):
    removed = await service.remove_word(session, chat_id=702, word="nothing")
    assert removed is False


async def test_filters_are_scoped_per_chat(session):
    await service.add_word(session, chat_id=703, word="a", added_by=1)
    await service.add_word(session, chat_id=704, word="b", added_by=1)
    words_703 = await service.get_filtered_words(session, 703)
    words_704 = await service.get_filtered_words(session, 704)
    assert words_703 == ["a"]
    assert words_704 == ["b"]
