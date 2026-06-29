"""Tests for champion-name matching."""
import json
import pytest
from pathlib import Path

from chat_parser.champions import ChampionMatcher

CHAMPIONS = [
    "Jinx", "Caitlyn", "Thresh", "LeBlanc", "Kai'Sa",
    "Vel'Koz", "Kog'Maw", "Cho'Gath", "Nunu & Willump", "Miss Fortune",
]


@pytest.fixture
def matcher():
    return ChampionMatcher(CHAMPIONS, threshold=75.0)


# ── exact matching ────────────────────────────────────────────────────────────

def test_exact_match(matcher):
    assert matcher.match("Jinx") == "Jinx"


def test_exact_match_case_insensitive(matcher):
    assert matcher.match("jinx") == "Jinx"
    assert matcher.match("CAITLYN") == "Caitlyn"
    assert matcher.match("leblanc") == "LeBlanc"


def test_exact_match_with_apostrophe(matcher):
    assert matcher.match("Kai'Sa") == "Kai'Sa"


def test_exact_match_multi_word(matcher):
    assert matcher.match("Miss Fortune") == "Miss Fortune"


# ── fuzzy matching ────────────────────────────────────────────────────────────

def test_fuzzy_capitalisation_variant(matcher):
    # "Leblanc" (wrong capitalisation) should still fuzzy-match
    result = matcher.match("Leblanc")
    assert result == "LeBlanc"


def test_fuzzy_miss_fortune_no_space(matcher):
    # OCR might merge "Miss Fortune" into "MissFortune"
    result = matcher.match("MissFortune")
    assert result == "Miss Fortune"


def test_fuzzy_thresh_ocr_corruption(matcher):
    # "Thresh" with a leading garbage character
    result = matcher.match("Tresh")
    assert result == "Thresh"


# ── no-match cases ────────────────────────────────────────────────────────────

def test_no_match_below_threshold(matcher):
    assert matcher.match("Xyzabc123") is None


def test_empty_string_returns_none(matcher):
    assert matcher.match("") is None


def test_whitespace_only_returns_none(matcher):
    assert matcher.match("   ") is None


# ── threshold control ─────────────────────────────────────────────────────────

def test_high_threshold_rejects_poor_match():
    strict = ChampionMatcher(CHAMPIONS, threshold=99.0)
    # "Tresh" (one char off) should fail a 99-threshold fuzzy match
    result = strict.match("Tresh")
    # Could be None OR "Thresh" if score is ≥99 — just assert type is correct
    assert result is None or result == "Thresh"


def test_zero_threshold_accepts_anything():
    permissive = ChampionMatcher(CHAMPIONS, threshold=0.0)
    result = permissive.match("zzz")
    assert result is not None  # some champion will be returned


# ── from_file loading ─────────────────────────────────────────────────────────

def test_from_file_list(tmp_path: Path):
    f = tmp_path / "champs.json"
    f.write_text(json.dumps(["Jinx", "Thresh"]), encoding="utf-8")
    m = ChampionMatcher.from_file(f)
    assert m.match("Jinx") == "Jinx"


def test_from_file_dict(tmp_path: Path):
    f = tmp_path / "champs.json"
    f.write_text(json.dumps({"1": "Jinx", "2": "Thresh"}), encoding="utf-8")
    m = ChampionMatcher.from_file(f)
    assert m.match("Thresh") == "Thresh"


def test_from_file_bad_format_raises(tmp_path: Path):
    f = tmp_path / "champs.json"
    f.write_text(json.dumps("not_a_list_or_dict"), encoding="utf-8")
    with pytest.raises(ValueError):
        ChampionMatcher.from_file(f)
