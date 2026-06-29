from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)


class ChampionMatcher:
    def __init__(self, champion_names: List[str], threshold: float = 80.0) -> None:
        self.champion_names = [n for n in champion_names if n]
        self.threshold = threshold
        self._lower_map: Dict[str, str] = {n.lower(): n for n in self.champion_names}

    @classmethod
    def from_file(cls, path: Path, threshold: float = 80.0) -> "ChampionMatcher":
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list):
            names: List[str] = data
        elif isinstance(data, dict):
            names = list(data.values())
        else:
            raise ValueError(f"Unexpected format in {path}: expected list or dict of champion names")
        logger.info("Loaded %d champion names from %s", len(names), path)
        return cls(names, threshold)

    def match(self, text: str) -> Optional[str]:
        if not text:
            return None
        stripped = text.strip()
        if not stripped:
            return None

        # Exact match (case-insensitive)
        lower = stripped.lower()
        if lower in self._lower_map:
            return self._lower_map[lower]

        # Fuzzy match via rapidfuzz WRatio (handles spacing, token order, etc.)
        result = process.extractOne(stripped, self.champion_names, scorer=fuzz.WRatio)
        if result is not None and result[1] >= self.threshold:
            logger.debug("Fuzzy matched '%s' -> '%s' (score %.1f)", stripped, result[0], result[1])
            return result[0]

        return None
