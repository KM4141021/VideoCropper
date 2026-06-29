"""Tests for chat-line parsing logic."""
import pytest

from lol_chat_parser.champions import ChampionMatcher
from lol_chat_parser.parser import parse_chat_line


CHAMPIONS = ["Jinx", "Caitlyn", "Thresh", "LeBlanc", "Miss Fortune", "Kai'Sa"]


@pytest.fixture
def matcher():
    return ChampionMatcher(CHAMPIONS, threshold=75.0)


# ── basic format parsing ──────────────────────────────────────────────────────

def test_simple_format():
    result = parse_chat_line("Jinx: group mid")
    assert result is not None
    sender, champ, msg = result
    assert sender == "Jinx"
    assert msg == "group mid"


def test_all_prefix():
    result = parse_chat_line("[All] Jinx: gg")
    assert result is not None
    sender, champ, msg = result
    assert sender == "Jinx"
    assert msg == "gg"


def test_ally_prefix():
    result = parse_chat_line("[Ally] Caitlyn: push bot now")
    assert result is not None
    sender, champ, msg = result
    assert sender == "Caitlyn"
    assert msg == "push bot now"


def test_player_with_champion_in_parens():
    result = parse_chat_line("SummonerABC (Jinx): group mid")
    assert result is not None
    sender, champ, msg = result
    assert sender == "SummonerABC"
    assert msg == "group mid"


def test_champion_with_team_role():
    result = parse_chat_line("Jinx (Team): group")
    assert result is not None
    sender, champ, msg = result
    assert sender == "Jinx"
    assert msg == "group"


def test_all_role_in_parens():
    result = parse_chat_line("Thresh (All): nice game")
    assert result is not None
    sender, _, msg = result
    assert sender == "Thresh"
    assert msg == "nice game"


def test_message_with_colons_inside():
    result = parse_chat_line("Jinx: come bot: now")
    assert result is not None
    sender, _, msg = result
    assert sender == "Jinx"
    # everything after the first ": " is the message
    assert msg == "come bot: now"


# ── empty / non-chat lines ────────────────────────────────────────────────────

def test_empty_line_returns_none():
    assert parse_chat_line("") is None


def test_whitespace_only_returns_none():
    assert parse_chat_line("   ") is None


def test_no_colon_returns_none():
    assert parse_chat_line("just some random text") is None


# ── champion resolution ───────────────────────────────────────────────────────

def test_champion_resolved_via_matcher(matcher):
    result = parse_chat_line("Jinx: push bot", champion_matcher=matcher)
    assert result is not None
    _, champ, _ = result
    assert champ == "Jinx"


def test_champion_from_parens_via_matcher(matcher):
    result = parse_chat_line("PlayerXYZ (Jinx): go mid", champion_matcher=matcher)
    assert result is not None
    _, champ, _ = result
    assert champ == "Jinx"


def test_champion_via_player_map():
    player_map = {"SummonerXYZ": "Thresh"}
    result = parse_chat_line("SummonerXYZ: go help bot", player_map=player_map)
    assert result is not None
    _, champ, _ = result
    assert champ == "Thresh"


def test_unknown_sender_no_champion():
    result = parse_chat_line("RandomPlayer123: hello")
    assert result is not None
    _, champ, _ = result
    assert champ is None


def test_player_map_preferred_when_matcher_fails():
    player_map = {"NotAChamp": "LeBlanc"}
    result = parse_chat_line("NotAChamp: roam top", player_map=player_map)
    assert result is not None
    _, champ, _ = result
    assert champ == "LeBlanc"
