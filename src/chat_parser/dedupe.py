from __future__ import annotations

import re
import logging
from typing import Dict, List, Tuple

from .models import ChatMessage

logger = logging.getLogger(__name__)


def normalize_for_dedup(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def deduplicate(
    messages: List[ChatMessage],
    time_window: float = 5.0,
) -> List[ChatMessage]:
    """
    Remove duplicate messages seen within time_window seconds.

    Keeps the earliest instance of each (sender, chat) pair and retains
    the highest confidence score seen across duplicates.
    """
    sorted_msgs = sorted(messages, key=lambda m: m.timestamp_seconds)

    # (norm_sender, norm_chat) -> the ChatMessage object already appended
    seen: Dict[Tuple[str, str], ChatMessage] = {}
    result: List[ChatMessage] = []

    for msg in sorted_msgs:
        key = (
            normalize_for_dedup(msg.sender_raw),
            normalize_for_dedup(msg.chat),
        )
        if key in seen:
            prior = seen[key]
            if msg.timestamp_seconds - prior.timestamp_seconds <= time_window:
                # Duplicate within window — update best confidence in place
                if msg.confidence > prior.confidence:
                    prior.confidence = msg.confidence
                continue
        # New message or same content but outside the dedup window
        seen[key] = msg
        result.append(msg)

    logger.debug("Deduplication: %d → %d messages", len(messages), len(result))
    return result
