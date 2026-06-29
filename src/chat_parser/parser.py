from __future__ import annotations

import re
import logging
from typing import Dict, List, Optional, Tuple

from .champions import ChampionMatcher

logger = logging.getLogger(__name__)

# Compiled patterns for LoL chat formats (most specific first)
# [All] / [Ally] SenderName: message
_PAT_BRACKET_PREFIX = re.compile(r'^\[(?:All|Ally)\]\s+(.+?):\s+(.+)$', re.IGNORECASE)

# SenderName (Content): message  — e.g. "PlayerABC (Jinx): go bot" or "Jinx (Team): go"
_PAT_PAREN = re.compile(r'^(.+?)\s+\((.+?)\):\s+(.+)$')

# SenderName: message  — simple format
_PAT_SIMPLE = re.compile(r'^(.+?):\s+(.+)$')

_ROLE_KEYWORDS = {"team", "all", "ally"}


def parse_chat_line(
    raw_line: str,
    champion_matcher: Optional[ChampionMatcher] = None,
    player_map: Optional[Dict[str, str]] = None,
) -> Optional[Tuple[str, Optional[str], str]]:
    """
    Parse one OCR text line into (sender_raw, champion_or_None, message).
    Returns None if the line does not look like a chat message.
    """
    line = raw_line.strip()
    if not line:
        return None

    # Pattern 1: [All] / [Ally] prefix
    m = _PAT_BRACKET_PREFIX.match(line)
    if m:
        sender_raw = m.group(1).strip()
        message = m.group(2).strip()
        champion = _resolve_champion(sender_raw, None, champion_matcher, player_map)
        return sender_raw, champion, message

    # Pattern 2: Name (Content): message
    m = _PAT_PAREN.match(line)
    if m:
        sender_raw = m.group(1).strip()
        paren_content = m.group(2).strip()
        message = m.group(3).strip()
        if paren_content.lower() in _ROLE_KEYWORDS:
            # e.g. "Jinx (Team): push bot" — sender IS the champion name
            champion = _resolve_champion(sender_raw, None, champion_matcher, player_map)
        else:
            # e.g. "PlayerABC (Jinx): go mid" — paren content is the champion name
            champion = _resolve_champion(paren_content, sender_raw, champion_matcher, player_map)
        return sender_raw, champion, message

    # Pattern 3: Simple "Name: message"
    m = _PAT_SIMPLE.match(line)
    if m:
        sender_raw = m.group(1).strip()
        message = m.group(2).strip()
        champion = _resolve_champion(sender_raw, None, champion_matcher, player_map)
        return sender_raw, champion, message

    return None


def _resolve_champion(
    name: str,
    player_name: Optional[str],
    matcher: Optional[ChampionMatcher],
    player_map: Optional[Dict[str, str]],
) -> Optional[str]:
    # 1. Try exact/fuzzy champion match on the name itself
    if matcher:
        result = matcher.match(name)
        if result:
            return result

    # 2. Try player_map with player_name as key (when name is the champion slot)
    if player_map and player_name and player_name in player_map:
        return player_map[player_name]

    # 3. Try player_map with name itself as key
    if player_map and name in player_map:
        return player_map[name]

    return None


def lines_from_ocr_results(ocr_results: list) -> List[Tuple[str, float]]:
    """Convert a list of OCRResult objects into (text, confidence) tuples."""
    return [(r.text, r.confidence) for r in ocr_results if r.text.strip()]
