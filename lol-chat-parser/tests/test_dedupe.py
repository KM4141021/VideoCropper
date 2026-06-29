"""Tests for duplicate-message suppression."""
import pytest

from lol_chat_parser.dedupe import deduplicate, normalize_for_dedup
from lol_chat_parser.models import ChatMessage


def _msg(ts: float, sender: str, chat: str, confidence: float = 0.9) -> ChatMessage:
    return ChatMessage(
        timestamp_seconds=ts,
        sender_raw=sender,
        chat=chat,
        confidence=confidence,
        raw_ocr=f"{sender}: {chat}",
    )


# ── normalisation ─────────────────────────────────────────────────────────────

def test_normalize_lowercases():
    assert normalize_for_dedup("JINX") == "jinx"


def test_normalize_strips_punctuation():
    assert normalize_for_dedup("Jinx!") == "jinx"
    assert normalize_for_dedup("Group, mid.") == "group mid"


def test_normalize_collapses_whitespace():
    assert normalize_for_dedup("  hello   world  ") == "hello world"


# ── deduplication behaviour ───────────────────────────────────────────────────

def test_exact_duplicate_within_window_removed():
    msgs = [_msg(0.0, "Jinx", "group mid"), _msg(2.0, "Jinx", "group mid")]
    result = deduplicate(msgs, time_window=5.0)
    assert len(result) == 1
    assert result[0].timestamp_seconds == 0.0


def test_duplicate_outside_window_kept():
    msgs = [_msg(0.0, "Jinx", "group mid"), _msg(10.0, "Jinx", "group mid")]
    result = deduplicate(msgs, time_window=5.0)
    assert len(result) == 2


def test_best_confidence_retained():
    msgs = [
        _msg(0.0, "Jinx", "group mid", confidence=0.70),
        _msg(1.5, "Jinx", "group mid", confidence=0.95),
    ]
    result = deduplicate(msgs, time_window=5.0)
    assert len(result) == 1
    assert result[0].confidence == pytest.approx(0.95)


def test_first_occurrence_kept():
    msgs = [_msg(0.0, "Jinx", "go bot"), _msg(1.0, "Jinx", "go bot")]
    result = deduplicate(msgs, time_window=5.0)
    assert result[0].timestamp_seconds == pytest.approx(0.0)


def test_different_senders_not_deduped():
    msgs = [_msg(0.0, "Jinx", "push bot"), _msg(0.5, "Caitlyn", "push bot")]
    result = deduplicate(msgs, time_window=5.0)
    assert len(result) == 2


def test_different_messages_not_deduped():
    msgs = [_msg(0.0, "Jinx", "push bot"), _msg(0.5, "Jinx", "group mid")]
    result = deduplicate(msgs, time_window=5.0)
    assert len(result) == 2


def test_case_insensitive_dedup():
    msgs = [_msg(0.0, "Jinx", "Push Bot!"), _msg(1.0, "jinx", "push bot")]
    result = deduplicate(msgs, time_window=5.0)
    assert len(result) == 1


def test_empty_list_returns_empty():
    assert deduplicate([]) == []


def test_single_message_unchanged():
    msgs = [_msg(5.0, "Thresh", "peel")]
    result = deduplicate(msgs, time_window=5.0)
    assert len(result) == 1
    assert result[0].sender_raw == "Thresh"


def test_triple_duplicate_only_first_kept():
    msgs = [
        _msg(0.0, "Jinx", "gg", confidence=0.8),
        _msg(1.0, "Jinx", "gg", confidence=0.9),
        _msg(2.0, "Jinx", "gg", confidence=0.7),
    ]
    result = deduplicate(msgs, time_window=5.0)
    assert len(result) == 1
    assert result[0].confidence == pytest.approx(0.9)
