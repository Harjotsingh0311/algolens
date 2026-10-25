from __future__ import annotations

from typing import Any

import gradio as gr
import pytest
from fastapi.testclient import TestClient

import app.app as app_module


def make_test_server():
    with gr.Blocks() as blocks:
        gr.Markdown("AlgoLens health endpoint test.")
    return app_module.create_server_app(blocks)


def test_healthz_reports_process_liveness_without_corpus_readiness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_corpus_check() -> dict[str, Any]:
        raise AssertionError("Liveness must not inspect corpus or providers.")

    monkeypatch.setattr(app_module, "corpus_readiness", failing_corpus_check)
    client = TestClient(make_test_server())

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "algolens"}


def test_readyz_returns_503_when_corpus_is_in_safe_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        app_module,
        "corpus_readiness",
        lambda: {
            "candidate_passages": 2,
            "eligible_passages": 0,
            "message": "0 of 2 child passages are explicitly approved.",
        },
    )
    client = TestClient(make_test_server())

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["status"] == "safe_mode"
    assert response.json()["ready"] is False
    assert response.json()["answer_generation_enabled"] is False
    assert response.json()["candidate_passages"] == 2
    assert response.json()["eligible_passages"] == 0


def test_readyz_returns_503_when_corpus_cannot_be_checked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        app_module,
        "corpus_readiness",
        lambda: {
            "candidate_passages": 0,
            "eligible_passages": 0,
            "message": "Corpus readiness could not be checked. Diagnostic type: ValueError.",
        },
    )
    client = TestClient(make_test_server())

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["status"] == "error"
    assert response.json()["ready"] is False
    assert "ValueError" not in response.text


def test_readyz_returns_200_after_runtime_initializes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        app_module,
        "corpus_readiness",
        lambda: {
            "candidate_passages": 1,
            "eligible_passages": 1,
            "message": "1 of 1 child passages are explicitly approved.",
        },
    )
    monkeypatch.setattr(
        app_module,
        "get_runtime",
        lambda: (
            object(),
            {
                "candidate_passages": 1,
                "eligible_passages": 1,
                "message": "Grounded-answer runtime initialized.",
            },
        ),
    )
    client = TestClient(make_test_server())

    response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["ready"] is True
    assert response.json()["answer_generation_enabled"] is True


def test_mounted_gradio_ui_still_serves_root_page() -> None:
    client = TestClient(make_test_server())

    response = client.get("/")

    assert response.status_code == 200
    assert "gradio" in response.text.casefold()
