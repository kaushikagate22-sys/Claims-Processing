"""Tests for multi-provider LLM selection (no network calls)."""
from core.tools.llm_client import LLMClient, resolve_provider


def test_resolve_explicit_wins():
    assert resolve_provider("openai", None, None) == "openai"
    assert resolve_provider("anthropic", "k", "k") == "anthropic"
    assert resolve_provider("offline", "k", "k") == "offline"


def test_resolve_autodetect_openai_preferred():
    assert resolve_provider(None, "openai-key", "anthropic-key") == "openai"


def test_resolve_autodetect_anthropic():
    assert resolve_provider(None, None, "anthropic-key") == "anthropic"


def test_resolve_offline_when_no_keys():
    assert resolve_provider(None, None, None) == "offline"


def test_client_offline_when_no_keys(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    c = LLMClient()
    assert c.mode == "offline"


def test_client_picks_openai_when_key_present(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    # Constructing the OpenAI client does NOT make a network call.
    c = LLMClient()
    assert c.mode in ("openai", "offline")  # openai if SDK installed
    if c.mode == "openai":
        assert c.model == "gpt-4o-mini"


def test_offline_extract_still_works(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    c = LLMClient()
    out = c.extract_json(
        "Policy Number: ABC-123\nClaim Amount: 5000",
        {"policy_number": "the id", "claim_amount": "the amount"},
    )
    assert out["policy_number"] == "ABC-123"
