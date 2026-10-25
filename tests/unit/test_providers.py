from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from algolens.contracts import CitationReference, Hit, Passage
from algolens.providers import OpenAICompatibleProvider


@pytest.fixture(autouse=True)
def isolate_dotenv_loading(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep provider unit tests independent of any local .env file."""
    monkeypatch.setattr(
        "algolens.providers.load_dotenv",
        lambda **kwargs: False,
    )


def eligible_hit() -> Hit:
    passage = Passage(
        id="passage-001",
        lecture=6,
        kind="notes",
        text="Randomized Quicksort selects a pivot at random.",
        section="Randomized Quicksort",
        page=5,
        citation=CitationReference(
            kind="pdf_page",
            display="p. 5",
            page_start=5,
            page_end=5,
        ),
        source_id="L06_TYPED_NOTES",
        source_sha256="a" * 64,
        review_status="reviewed",
        eligible_for_answer=True,
    )
    return Hit(passage=passage, score=2.5, ranks={"hybrid": 1})


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self.payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def provider_payload(content: str) -> dict[str, Any]:
    return {
        "choices": [
            {
                "message": {
                    "content": content,
                }
            }
        ]
    }


def test_provider_parses_structured_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def fake_urlopen(request: Any, timeout: float) -> FakeResponse:
        calls.append(
            {
                "url": request.full_url,
                "headers": dict(request.header_items()),
                "body": json.loads(request.data.decode("utf-8")),
                "timeout": timeout,
            }
        )
        return FakeResponse(
            provider_payload(
                json.dumps(
                    {
                        "answer_md": "Randomized Quicksort chooses a random pivot [p. 5].",
                        "claims": [
                            {
                                "text": "It chooses a random pivot.",
                                "cites": ["passage-001"],
                                "support": "supported",
                            }
                        ],
                    }
                )
            )
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    provider = OpenAICompatibleProvider(
        base_url="http://localhost:11434/v1",
        model="test-model",
        timeout_seconds=3,
    )
    result = provider.generate(
        "How is the pivot selected?",
        [eligible_hit()],
        allow_partial=False,
    )

    assert result.claims[0].cites == ["passage-001"]
    assert result.claims[0].support == "supported"
    assert len(calls) == 1
    assert calls[0]["url"] == "http://localhost:11434/v1/chat/completions"
    assert calls[0]["body"]["model"] == "test-model"
    assert calls[0]["timeout"] == 3
    assert "passage-001" in calls[0]["body"]["messages"][1]["content"]
    assert (
        "Randomized Quicksort selects a pivot at random."
        in (calls[0]["body"]["messages"][1]["content"])
    )


def test_provider_does_not_call_network_without_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_urlopen(*args: Any, **kwargs: Any) -> FakeResponse:
        raise AssertionError("Network must not be called without evidence.")

    monkeypatch.setattr("urllib.request.urlopen", forbidden_urlopen)
    provider = OpenAICompatibleProvider(
        base_url="http://localhost:11434/v1",
        model="test-model",
    )

    with pytest.raises(ValueError, match="evidence"):
        provider.generate("Question?", [], allow_partial=False)


def test_provider_rejects_unapproved_passages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unreviewed = Passage(
        id="candidate-001",
        lecture=6,
        kind="notes",
        text="Candidate text.",
        section="Candidate",
    )
    hit = Hit(passage=unreviewed, score=10.0)

    def forbidden_urlopen(*args: Any, **kwargs: Any) -> FakeResponse:
        raise AssertionError("Unapproved evidence must never reach the network.")

    monkeypatch.setattr("urllib.request.urlopen", forbidden_urlopen)
    provider = OpenAICompatibleProvider(
        base_url="http://localhost:11434/v1",
        model="test-model",
    )

    with pytest.raises(ValueError, match="approved"):
        provider.generate("Question?", [hit], allow_partial=False)


def test_provider_rejects_malformed_model_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: FakeResponse(provider_payload("not json")),
    )
    provider = OpenAICompatibleProvider(
        base_url="http://localhost:11434/v1",
        model="test-model",
    )

    with pytest.raises(ValueError, match="JSON"):
        provider.generate("Question?", [eligible_hit()], allow_partial=False)


def test_provider_rejects_missing_chat_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: FakeResponse({"choices": []}),
    )
    provider = OpenAICompatibleProvider(
        base_url="http://localhost:11434/v1",
        model="test-model",
    )

    with pytest.raises(ValueError, match="content"):
        provider.generate("Question?", [eligible_hit()], allow_partial=False)


def test_from_env_configures_ollama_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ALGOLENS_PROVIDER", raising=False)
    monkeypatch.delenv("ALGOLENS_MODEL", raising=False)
    monkeypatch.delenv("ALGOLENS_BASE_URL", raising=False)
    monkeypatch.delenv("ALGOLENS_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)

    provider = OpenAICompatibleProvider.from_env()

    assert provider.base_url == "http://localhost:11434/v1"
    assert provider.api_key is None


def test_from_env_requires_groq_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGOLENS_PROVIDER", "groq")
    monkeypatch.delenv("ALGOLENS_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        OpenAICompatibleProvider.from_env()


def test_provider_rejects_invalid_timeout() -> None:
    with pytest.raises(ValueError, match="timeout"):
        OpenAICompatibleProvider(
            base_url="http://localhost:11434/v1",
            model="test-model",
            timeout_seconds=0,
        )


def test_provider_adds_bearer_auth_when_key_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict[str, Any]] = []

    def fake_urlopen(request: Any, timeout: float) -> FakeResponse:
        captured.append(
            {
                "headers": dict(request.header_items()),
                "body": json.loads(request.data.decode("utf-8")),
            }
        )
        return FakeResponse(
            provider_payload(
                json.dumps(
                    {
                        "answer_md": "A cited answer [p. 5].",
                        "claims": [
                            {
                                "text": "A supported claim.",
                                "cites": ["passage-001"],
                                "support": "supported",
                            }
                        ],
                    }
                )
            )
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = OpenAICompatibleProvider(
        base_url="https://api.groq.com/openai/v1",
        model="test-model",
        api_key="test-key",
    )

    provider.generate("Question?", [eligible_hit()], allow_partial=False)

    captured_headers = {key.lower(): value for key, value in captured[0]["headers"].items()}
    captured_body = captured[0]["body"]

    assert captured_headers["authorization"] == "Bearer test-key"
    assert captured_headers["user-agent"] == "AlgoLens/0.1.0"
    assert captured_body["reasoning_effort"] == "low"
    assert captured_body["max_completion_tokens"] == 4096


def test_from_env_supports_llm_provider_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ALGOLENS_PROVIDER", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.delenv("ALGOLENS_BASE_URL", raising=False)
    monkeypatch.delenv("ALGOLENS_MODEL", raising=False)
    monkeypatch.delenv("ALGOLENS_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "test-key-not-a-real-secret")

    provider = OpenAICompatibleProvider.from_env()

    assert provider.base_url == "https://api.groq.com/openai/v1"
    assert provider.model == "openai/gpt-oss-120b"
    assert provider.api_key == "test-key-not-a-real-secret"


def test_from_env_supports_ollama_base_url_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ALGOLENS_PROVIDER", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.delenv("ALGOLENS_BASE_URL", raising=False)
    monkeypatch.setenv(
        "OLLAMA_BASE_URL",
        "http://127.0.0.1:11434/v1",
    )
    monkeypatch.delenv("ALGOLENS_MODEL", raising=False)
    monkeypatch.delenv("ALGOLENS_API_KEY", raising=False)

    provider = OpenAICompatibleProvider.from_env()

    assert provider.base_url == "http://127.0.0.1:11434/v1"
    assert provider.model == "llama3.2"
    assert provider.api_key is None


def test_from_env_loads_dotenv_from_project_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def fake_load_dotenv(*, dotenv_path: str | Path, override: bool) -> bool:
        observed["path"] = Path(dotenv_path)
        observed["override"] = override
        return True

    monkeypatch.setattr("algolens.providers.load_dotenv", fake_load_dotenv)
    monkeypatch.setenv("ALGOLENS_PROVIDER", "ollama")
    monkeypatch.delenv("ALGOLENS_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("ALGOLENS_MODEL", raising=False)
    monkeypatch.delenv("ALGOLENS_API_KEY", raising=False)

    provider = OpenAICompatibleProvider.from_env()

    expected_path = Path(__file__).resolve().parents[2] / ".env"
    assert observed["path"] == expected_path
    assert observed["override"] is False
    assert provider.base_url == "http://localhost:11434/v1"


def test_from_env_supports_optional_fallback_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGOLENS_FALLBACK_PROVIDER", "groq")
    monkeypatch.setenv("ALGOLENS_FALLBACK_API_KEY", "test-fallback-key")
    monkeypatch.delenv("ALGOLENS_FALLBACK_BASE_URL", raising=False)
    monkeypatch.delenv("ALGOLENS_FALLBACK_MODEL", raising=False)
    monkeypatch.delenv("ALGOLENS_FALLBACK_TIMEOUT_SECONDS", raising=False)

    provider = OpenAICompatibleProvider.from_env(prefix="ALGOLENS_FALLBACK_")

    assert provider.base_url == "https://api.groq.com/openai/v1"
    assert provider.model == "openai/gpt-oss-120b"
    assert provider.api_key == "test-fallback-key"
    assert provider.timeout_seconds == 30.0
