from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import gradio as gr
import uvicorn
import yaml
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from algolens.answer_cache import CachedAnswerProvider
from algolens.fallback_provider import FallbackAnswerProvider
from algolens.grounded_answering import GroundedAnswerService
from algolens.providers import OpenAICompatibleProvider
from algolens.retrieval.bm25 import BM25Index, is_answer_eligible
from algolens.retrieval.dense import DenseIndex
from algolens.retrieval.hybrid import HybridIndex
from algolens.retrieval.pipeline import RetrievalPipeline
from algolens.retrieval.rerank import CrossEncoderReranker
from algolens.runtime import build_grounded_answer_service

ROOT = Path(__file__).resolve().parents[1]
CHILDREN_PATH = ROOT / "corpus" / "processed" / "reviewed_chunks" / "children.jsonl"
MANIFEST_PATH = ROOT / "corpus" / "manifest.yaml"
MAX_QUESTION_LENGTH = 10_000

SAFE_ABSTENTION = (
    "I cannot provide a reliable lecture answer yet. "
    "AlgoLens requires explicitly approved evidence before generation."
)


def load_child_chunks() -> list[dict[str, Any]]:
    """Load the canonical child-chunk file without changing approval metadata."""
    if not CHILDREN_PATH.exists():
        return []

    chunks: list[dict[str, Any]] = []
    with CHILDREN_PATH.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in child chunks at line {line_number}.") from exc

            if not isinstance(value, dict):
                raise ValueError(f"Expected a JSON object at child-chunk line {line_number}.")
            chunks.append(value)

    return chunks


def filter_answer_eligible_chunks(
    chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Require all explicit approval flags; never promote a candidate automatically."""
    return [
        chunk
        for chunk in chunks
        if is_answer_eligible(chunk)
        and chunk.get("eligible_for_answer") is True
        and chunk.get("retrieval_eligible") is True
    ]


def load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        return {}
    value = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def corpus_readiness() -> dict[str, Any]:
    try:
        chunks = load_child_chunks()
        eligible = filter_answer_eligible_chunks(chunks)
        return {
            "candidate_passages": len(chunks),
            "eligible_passages": len(eligible),
            "message": (
                f"{len(eligible)} of {len(chunks)} child passages are explicitly "
                "approved for retrieval and answer generation."
            ),
        }
    except Exception as exc:
        # Avoid exposing internal paths or sensitive configuration in the UI.
        return {
            "candidate_passages": 0,
            "eligible_passages": 0,
            "message": (
                f"Corpus readiness could not be checked. Diagnostic type: {type(exc).__name__}."
            ),
        }


def startup_status() -> str:
    readiness = corpus_readiness()
    total = readiness["candidate_passages"]
    eligible = readiness["eligible_passages"]

    if eligible == 0:
        return (
            "**SAFE MODE ACTIVE**  \\n"
            f"**{eligible} of {total} passages approved.** "
            "Answer generation is locked because no passage has all "
            "the required approval signals. The app is running; "
            "this is the intended evidence-safety state."
        )

    return (
        "**CORPUS GATE OPEN**  \\n"
        f"**{eligible} of {total} passages approved.** "
        "The app can attempt a grounded response, subject to "
        "runtime checks and claim verification."
    )


def build_runtime() -> tuple[GroundedAnswerService | None, dict[str, Any]]:
    """Build the real retrieval-to-grounded-answer runtime only when evidence is approved."""
    try:
        chunks = load_child_chunks()
        eligible = filter_answer_eligible_chunks(chunks)
        status: dict[str, Any] = {
            "candidate_passages": len(chunks),
            "eligible_passages": len(eligible),
        }

        if not eligible:
            status["message"] = (
                "No child passages have all three required approval signals: "
                "approved review status, eligible_for_answer=true, and "
                "retrieval_eligible=true."
            )
            return None, status

        manifest = load_manifest()
        corpus_version = str(manifest.get("version", "unknown"))

        primary_provider = OpenAICompatibleProvider.from_env()
        configured_providers = [primary_provider]
        fallback_warning: str | None = None
        if os.getenv("ALGOLENS_FALLBACK_PROVIDER", "").strip():
            try:
                configured_providers.append(
                    OpenAICompatibleProvider.from_env(prefix="ALGOLENS_FALLBACK_")
                )
            except Exception as exc:
                # Keep the primary provider usable if optional fallback settings
                # are malformed; expose only the diagnostic exception type.
                fallback_warning = type(exc).__name__
                print(f"AlgoLens fallback configuration failed: {fallback_warning}")

        provider_chain = FallbackAnswerProvider(configured_providers)
        model_id = primary_provider.model
        cache_namespace = "provider-chain:" + "->".join(
            f"{item.base_url}|{item.model}" for item in configured_providers
        )
        cached_provider = CachedAnswerProvider(
            provider_chain,
            corpus_version=corpus_version,
            model_id=cache_namespace,
            cache_path=os.getenv("ALGOLENS_CACHE_PATH") or None,
        )
        bm25 = BM25Index(eligible, include_unreviewed=False)
        dense = DenseIndex(eligible, include_unreviewed=False)
        hybrid = HybridIndex(
            eligible,
            bm25_index=bm25,
            dense_index=dense,
            include_unreviewed=False,
        )
        reranker = CrossEncoderReranker(include_unreviewed=False)
        pipeline = RetrievalPipeline(
            hybrid_index=hybrid,
            reranker=reranker,
            candidate_k=20,
            include_unreviewed=False,
        )

        service = build_grounded_answer_service(
            retrieval_pipeline=pipeline,
            provider=cached_provider,
            corpus_version=corpus_version,
            model_id=model_id,
            top_k=6,
        )
        status["message"] = "Grounded-answer runtime initialized."
        status["model"] = model_id
        if len(configured_providers) > 1:
            status["fallback_models"] = [item.model for item in configured_providers[1:]]
        if fallback_warning is not None:
            status["fallback_warning"] = fallback_warning
        return service, status

    except Exception as exc:
        # Keep API keys, request headers, and internal exception messages out of the UI.
        print(f"AlgoLens runtime initialization failed: {type(exc).__name__}")
        return None, {
            "candidate_passages": 0,
            "eligible_passages": 0,
            "message": (
                "Runtime initialization failed. Check the local environment and "
                f"server console. Diagnostic type: {type(exc).__name__}."
            ),
        }


@lru_cache(maxsize=1)
def get_runtime() -> tuple[GroundedAnswerService | None, dict[str, Any]]:
    """Initialize once per app process; restart after changing corpus approvals."""
    return build_runtime()


def source_link(passage: Any, sources: dict[str, dict[str, Any]]) -> str | None:
    source_id = getattr(passage, "source_id", None)
    source_record = sources.get(source_id, {}) if isinstance(source_id, str) else {}
    url = getattr(passage, "source_url", None) or source_record.get("url")

    if not isinstance(url, str) or not url.startswith(("https://", "http://")):
        return None

    citation = getattr(passage, "citation", None)
    page = getattr(citation, "page_start", None) or getattr(passage, "page", None)
    if isinstance(page, int) and not isinstance(page, bool) and page > 0:
        return f"{url.split('#', 1)[0]}#page={page}"

    timestamp = getattr(citation, "start_seconds", None) or getattr(passage, "t_start", None)
    if (
        isinstance(timestamp, (int, float))
        and not isinstance(timestamp, bool)
        and timestamp >= 0
        and "youtube.com/watch" in url
    ):
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}t={int(timestamp)}s"

    return url


def format_evidence(answer: Any) -> str:
    if not answer.sources:
        topics = getattr(answer, "closest_topics", [])
        suffix = ""
        if topics:
            suffix = "\n\n**Closest covered topics:** " + ", ".join(topics)
        return (
            "No evidence passage was released with this answer. "
            "AlgoLens abstains when evidence is absent, unapproved, or fails verification." + suffix
        )

    manifest = load_manifest()
    records = {
        item.get("id"): item
        for item in manifest.get("sources", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }

    sections: list[str] = []
    for hit in answer.sources:
        passage = hit.passage
        passage_id = getattr(passage, "id", "unknown passage")
        section = getattr(passage, "section", "") or "Lecture passage"
        page = getattr(passage, "page", None)
        citation = getattr(passage, "citation", None)
        display = getattr(citation, "display", None)
        locator = display or (f"p. {page}" if page else "source passage")
        url = source_link(passage, records)
        title = f"{section} ? {locator}"
        if url:
            title = f"[{title}]({url})"

        text = getattr(passage, "text", "")
        quoted = "\n".join(f"> {line}" for line in str(text).splitlines())
        sections.append(f"### {title}\n\n`{passage_id}`\n\n{quoted}")

    return "\n\n---\n\n".join(sections)


def answer_question(question: str) -> tuple[str, str, str, Any, Any]:
    """UI callback: return answer, status, evidence, claim report, and trace."""
    if not isinstance(question, str) or not question.strip():
        return (
            "Enter a question about the supplied lecture.",
            "?? Empty questions are not searched.",
            "No evidence retrieved.",
            [],
            {"status": "rejected", "reason": "empty_question"},
        )

    question = question.strip()
    if len(question) > MAX_QUESTION_LENGTH:
        return (
            "Your question is too long. Please shorten it and try again.",
            "?? Input rejected before retrieval.",
            "No evidence retrieved.",
            [],
            {
                "status": "rejected",
                "reason": "question_too_long",
                "maximum_characters": MAX_QUESTION_LENGTH,
            },
        )

    service, readiness = get_runtime()

    if service is None:
        eligible = readiness.get("eligible_passages", 0)
        reason = str(readiness.get("message", "The runtime is unavailable."))

        if eligible == 0:
            answer_text = (
                SAFE_ABSTENTION + "\n\n**Why answering is locked:** no child passages have all "
                "three required approval signals. Review the source content and "
                "record explicit retrieval approval before restarting the app."
            )
            status_text = (
                "**CORPUS GATE: CLOSED**\n\n"
                + reason
                + "\n\nNo passage was sent to the language model."
            )
            trace = {
                "status": "not_ready",
                "reason": "no_approved_evidence",
                **readiness,
            }
        else:
            answer_text = (
                SAFE_ABSTENTION + "\n\nThe corpus has approved passages, but the answering "
                "runtime could not initialize. Check the server console."
            )
            status_text = "**RUNTIME: UNAVAILABLE**\n\n" + reason + "\n\nNo answer was returned."
            trace = {
                "status": "not_ready",
                "reason": "runtime_initialization_failed",
                **readiness,
            }

        return (
            answer_text,
            status_text,
            "No evidence was released for this request.",
            [],
            trace,
        )

    try:
        answer = service.answer(question)
    except Exception as exc:
        # Never expose stack traces, API headers, or secret-bearing exception text to visitors.
        print(f"AlgoLens request failed: {type(exc).__name__}")
        return (
            SAFE_ABSTENTION,
            "?? The request could not be completed safely. Try again later.",
            "Evidence was withheld.",
            [],
            {"status": "error", "diagnostic_type": type(exc).__name__},
        )

    if answer.status == "answered":
        status = "**ANSWER VERIFIED**\n\nThe response passed the independent claim-grounding check."
    elif answer.status == "partial":
        status = "**PARTIAL ANSWER**\n\nOnly claims that passed the support checks were returned."
    elif answer.status == "sources_only":
        status = "**SOURCES ONLY**\n\nNo generated answer was released."
    else:
        status = (
            "**ABSTAINED**\n\nA reliable answer could not be validated from the available evidence."
        )

    claims = [
        {
            "claim": claim.text,
            "support": claim.support or "unlabelled",
            "citations": claim.cites,
        }
        for claim in answer.claims
    ]
    trace = {
        "status": answer.status,
        "corpus_version": answer.corpus_version,
        "model": answer.model,
        "latency_ms": answer.latency_ms,
        "closest_topics": answer.closest_topics,
        "claim_count": len(answer.claims),
        "claims": claims,
    }

    return answer.answer_md, status, format_evidence(answer), claims, trace


APP_CSS = ""
APP_THEME: Any = None


def create_app() -> gr.Blocks:
    global APP_CSS, APP_THEME
    css = r"""
    :root {
        color-scheme: light;
    }

    body {
        background: #f2f5fb !important;
    }

    .gradio-container {
        max-width: 1360px !important;
        margin: 0 auto !important;
        padding: 24px !important;
        background: #f2f5fb !important;
        color: #1b2440 !important;
    }

    footer {
        display: none !important;
    }

    .hero {
        position: relative;
        overflow: hidden;
        margin: 0 0 18px 0;
        padding: 30px 34px 26px 34px;
        border: 1px solid rgba(255,255,255,0.22);
        border-radius: 25px;
        color: #ffffff !important;
        background:
            radial-gradient(circle at 88% 18%, rgba(61,218,203,0.24), transparent 27%),
            radial-gradient(circle at 70% 110%, rgba(158,117,255,0.30), transparent 37%),
            linear-gradient(125deg, #171a3a 0%, #302566 54%, #16566a 100%);
        box-shadow: 0 18px 48px rgba(35, 42, 92, 0.18);
    }

    .hero * {
        color: #ffffff !important;
    }

    .hero-top {
        display: flex;
        align-items: center;
        gap: 13px;
        flex-wrap: wrap;
        margin-bottom: 26px;
    }

    .brand-mark {
        width: 44px;
        height: 44px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: 14px;
        background: rgba(255,255,255,0.14);
        border: 1px solid rgba(255,255,255,0.28);
        font-weight: 850;
        font-size: 15px;
        letter-spacing: -1px;
    }

    .brand-name {
        font-size: 17px;
        font-weight: 800;
        letter-spacing: -0.3px;
    }

    .hero-kicker {
        font-size: 10px;
        font-weight: 800;
        letter-spacing: 1.7px;
        opacity: 0.75;
        text-transform: uppercase;
    }

    .hero-chip {
        margin-left: auto;
        padding: 7px 11px;
        border: 1px solid rgba(255,255,255,0.23);
        border-radius: 999px;
        background: rgba(255,255,255,0.09);
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.7px;
    }

    .hero h1 {
        margin: 0 0 12px 0;
        font-size: clamp(28px, 4vw, 44px);
        line-height: 1.08;
        letter-spacing: -1.8px;
        font-weight: 850;
    }

    .hero h1 .accent {
        color: #85f0df !important;
    }

    .hero-description {
        max-width: 720px;
        margin: 0;
        font-size: 14px;
        line-height: 1.75;
        opacity: 0.86;
    }

    .hero-footer {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 24px;
    }

    .hero-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 11px;
        border-radius: 9px;
        background: rgba(255,255,255,0.09);
        border: 1px solid rgba(255,255,255,0.13);
        font-size: 11px;
        font-weight: 650;
    }

    .pill-dot {
        display: inline-block;
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: #85f0df;
    }

    .readiness-banner {
        margin: 0 0 17px 0 !important;
        padding: 12px 17px !important;
        border: 1px solid #e5e9f4 !important;
        border-left: 4px solid #e5a13a !important;
        border-radius: 13px !important;
        background: #fffaf0 !important;
        color: #62420c !important;
    }

    .readiness-banner p {
        margin: 0 !important;
        line-height: 1.65;
        font-size: 13px;
        color: #62420c !important;
    }

    .surface {
        padding: 20px !important;
        border: 1px solid #e4e8f2 !important;
        border-radius: 20px !important;
        background: #ffffff !important;
        box-shadow: 0 8px 28px rgba(30, 46, 90, 0.055);
    }

    .surface h3, .surface h4 {
        color: #202747 !important;
        letter-spacing: -0.35px;
    }

    .panel-kicker p {
        color: #777f9c !important;
        text-transform: uppercase;
        font-size: 10px !important;
        letter-spacing: 1.4px;
        font-weight: 800;
    }

    .section-help p {
        color: #6c7592 !important;
        font-size: 12px !important;
        line-height: 1.65;
    }

    .question-input textarea {
        min-height: 125px !important;
        border: 1px solid #dce2f0 !important;
        border-radius: 13px !important;
        background: #fbfcff !important;
        color: #1b2440 !important;
        line-height: 1.6 !important;
        box-shadow: none !important;
    }

    .question-input textarea:focus {
        border-color: #8e7bf0 !important;
        box-shadow: 0 0 0 3px rgba(142,123,240,0.13) !important;
    }

    .ask-button button {
        min-height: 48px;
        border: 0 !important;
        border-radius: 12px !important;
        background: linear-gradient(100deg, #6555db, #4d78d6) !important;
        box-shadow: 0 7px 18px rgba(86, 91, 210, 0.24);
        font-weight: 750 !important;
        letter-spacing: 0.1px;
    }

    .ask-button button:hover {
        filter: brightness(1.05);
        box-shadow: 0 10px 23px rgba(86, 91, 210, 0.31);
    }

    .result-status {
        margin-bottom: 12px !important;
        padding: 13px 15px !important;
        border: 1px solid #e5e9f4 !important;
        border-radius: 12px !important;
        background: #f7f8fd !important;
    }

    .result-status p {
        color: #414b70 !important;
        line-height: 1.6;
        font-size: 12px;
        margin: 0 !important;
    }

    .answer-output {
        min-height: 135px;
        padding: 9px 3px 4px 3px !important;
        color: #252d4c !important;
        line-height: 1.8;
    }

    .answer-output p, .evidence-output p {
        line-height: 1.8;
    }

    .stat-number {
        color: #282752;
        font-size: 31px;
        font-weight: 850;
        letter-spacing: -1.4px;
        line-height: 1.2;
    }

    .stat-label {
        color: #707995;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.9px;
        text-transform: uppercase;
    }

    .mini-rule {
        height: 1px;
        margin: 18px 0;
        background: #e9edf5;
    }

    .side-note {
        padding: 12px 13px;
        border: 1px solid #e4e7f5;
        border-radius: 12px;
        background: #f7f7ff;
        color: #535b7d;
        font-size: 12px;
        line-height: 1.7;
    }

    .gradio-container .tab-nav {
        gap: 7px;
        border-bottom: 1px solid #e3e7f1 !important;
        margin-bottom: 16px !important;
    }

    .gradio-container .tab-nav button {
        border-radius: 10px 10px 0 0 !important;
        color: #727b97 !important;
        font-weight: 700 !important;
    }

    .gradio-container .tab-nav button.selected {
        color: #5445c4 !important;
        border-bottom: 3px solid #7665e8 !important;
    }

    .gradio-container .form, .gradio-container input {
        border-color: #e1e6f1 !important;
    }

    .gradio-container .prose {
        color: #3f4867;
    }

    .app-footer {
        padding: 17px 4px 4px 4px;
        color: #848ba4;
        text-align: center;
        font-size: 11px;
        line-height: 1.8;
    }

    @media (max-width: 760px) {
        .gradio-container {
            padding: 12px !important;
        }
        .hero {
            padding: 23px 20px;
            border-radius: 19px;
        }
        .hero-chip {
            margin-left: 0;
        }
        .surface {
            padding: 15px !important;
        }
    }

    /* ALGOLENS_LIGHT_FIX_V2: readable surfaces in either browser theme. */
    :root,
    html,
    body {
        color-scheme: light !important;
    }

    .gradio-container,
    .gradio-container[data-theme="dark"],
    html[data-theme="dark"] .gradio-container {
        color-scheme: light !important;
        --body-background-fill: #f2f5fb !important;
        --body-background-fill-dark: #f2f5fb !important;
        --body-text-color: #1b2440 !important;
        --body-text-color-dark: #1b2440 !important;
        --background-fill-primary: #f2f5fb !important;
        --background-fill-primary-dark: #f2f5fb !important;
        --background-fill-secondary: #ffffff !important;
        --background-fill-secondary-dark: #ffffff !important;
        --block-background-fill: #ffffff !important;
        --block-background-fill-dark: #ffffff !important;
        --block-label-text-color: #202747 !important;
        --block-label-text-color-dark: #202747 !important;
        --input-background-fill: #fbfcff !important;
        --input-background-fill-dark: #fbfcff !important;
    }

    .gradio-container .surface,
    .gradio-container .surface .wrap,
    .gradio-container .surface .container,
    .gradio-container .surface .form,
    .gradio-container .surface .block:not(.ask-button):not(.result-status) {
        background-color: #ffffff !important;
        color: #202747 !important;
        border-color: #e4e8f2 !important;
    }

    .gradio-container .surface .prose,
    .gradio-container .surface .prose p,
    .gradio-container .surface .prose li,
    .gradio-container .surface label,
    .gradio-container .surface h1,
    .gradio-container .surface h2,
    .gradio-container .surface h3,
    .gradio-container .surface h4 {
        color: #202747 !important;
        opacity: 1 !important;
    }

    .gradio-container .surface .section-help,
    .gradio-container .surface .section-help *,
    .gradio-container .surface .panel-kicker,
    .gradio-container .surface .panel-kicker * {
        color: #65708f !important;
        opacity: 1 !important;
    }

    .gradio-container .surface .result-status {
        background-color: #f7f8fd !important;
        border-color: #e5e9f4 !important;
        color: #414b70 !important;
    }

    .gradio-container .surface .result-status * {
        color: #414b70 !important;
    }

    .gradio-container .surface textarea,
    .gradio-container .surface input {
        background-color: #fbfcff !important;
        color: #1b2440 !important;
        border-color: #dce2f0 !important;
    }

    .gradio-container .surface .ask-button button {
        background: linear-gradient(100deg, #6555db, #4d78d6) !important;
        color: #ffffff !important;
    }

    .gradio-container .readiness-banner,
    .gradio-container .readiness-banner * {
        background-color: #fffaf0;
        color: #62420c !important;
        opacity: 1 !important;
    }

    """

    theme = gr.themes.Soft(
        primary_hue="violet",
        secondary_hue="cyan",
        neutral_hue="slate",
    )

    APP_CSS = css
    APP_THEME = theme

    blocks_kwargs: dict[str, Any] = {
        "title": "AlgoLens | Citation-first RAG Tutor",
    }
    gradio_major = int(gr.__version__.split(".", maxsplit=1)[0])
    if gradio_major < 6:
        blocks_kwargs["theme"] = theme
        blocks_kwargs["css"] = css

    with gr.Blocks(**blocks_kwargs) as demo:
        gr.HTML(
            """
            <div class="hero">
              <div class="hero-top">
                <span class="brand-mark">AL</span>
                <span class="brand-name">AlgoLens</span>
                <span class="hero-kicker">Evidence-first learning</span>
                <span class="hero-chip">MIT 6.046J / LECTURE 06</span>
              </div>
              <h1>Learn the logic.<br><span class="accent">Trace the evidence.</span></h1>
              <p class="hero-description">
                A focused tutor for Randomized Quicksort. Explore concepts with
                source-located evidence, claim-level checks, and a deliberate
                abstention policy when the lecture material cannot support an answer.
              </p>
              <div class="hero-footer">
                <span class="hero-pill">
                  <span class="pill-dot"></span> Evidence-gated responses
                </span>
                <span class="hero-pill">Source-located citations</span>
                <span class="hero-pill">Claim-level verification</span>
              </div>
            </div>
            """
        )

        gr.Markdown(
            startup_status(),
            elem_classes=["readiness-banner"],
        )

        with gr.Tabs():
            with gr.Tab("Ask"):
                with gr.Row(equal_height=False):
                    with gr.Column(scale=7, min_width=320):
                        with gr.Group(elem_classes=["surface"]):
                            gr.Markdown(
                                "### Ask your lecture",
                                elem_classes=["panel-kicker"],
                            )
                            gr.Markdown(
                                "Ask one clear question. AlgoLens will only answer "
                                "from evidence that has passed the corpus approval gate.",
                                elem_classes=["section-help"],
                            )
                            question = gr.Textbox(
                                label="Your question",
                                placeholder=(
                                    "Why does a good pivot lead to Theta(n log n) expected runtime?"
                                ),
                                lines=4,
                                max_lines=8,
                                elem_classes=["question-input"],
                            )
                            ask = gr.Button(
                                "Analyze question",
                                variant="primary",
                                elem_classes=["ask-button"],
                            )
                            gr.Markdown(
                                "No outside web search is used to fill gaps in lecture evidence.",
                                elem_classes=["section-help"],
                            )

                        with gr.Group(elem_classes=["surface"]):
                            gr.Markdown(
                                "### Answer",
                                elem_classes=["panel-kicker"],
                            )
                            status = gr.Markdown(
                                "READY FOR INPUT\n\nSubmit a question to begin.",
                                elem_classes=["result-status"],
                            )
                            answer = gr.Markdown(
                                "Your grounded response will appear here. "
                                "When evidence is insufficient or unapproved, "
                                "AlgoLens will explain why it abstained.",
                                elem_classes=["answer-output"],
                            )

                    with gr.Column(scale=4, min_width=270):
                        with gr.Group(elem_classes=["surface"]):
                            gr.Markdown("### Corpus gate")
                            readiness = corpus_readiness()
                            gr.HTML(
                                f"""
                                <div style="padding:5px 0 7px 0">
                                  <div class="stat-number">
                         {readiness["eligible_passages"]} / {readiness["candidate_passages"]}
                       </div>
                                  <div class="stat-label">Passages approved for answering</div>
                                </div>
                                """
                            )
                            gr.Markdown(
                                readiness["message"],
                                elem_classes=["section-help"],
                            )
                            gr.HTML('<div class="mini-rule"></div>')
                            gr.Markdown(
                                """
                                **What unlocks answers?**

                                The source content must be reviewed and the chunk
                                must carry explicit approval flags. A passing test
                                suite alone does not approve source content.
                                """,
                                elem_classes=["section-help"],
                            )

                        with gr.Group(elem_classes=["surface"]):
                            gr.Markdown("### Try a question")
                            gr.Markdown(
                                "These are examples of the target topic. The current "
                                "corpus may still abstain until approval and "
                                "coverage are complete.",
                                elem_classes=["section-help"],
                            )
                            gr.Examples(
                                examples=[
                                    ["What is a good pivot in the lecture's analysis?"],
                                    ["Why is the expected number of attempts at most 2?"],
                                    ["How does the recurrence lead to Theta(n log n)?"],
                                ],
                                inputs=question,
                                label="Example prompts",
                                examples_per_page=3,
                            )

                gr.HTML(
                    """
                    <div class="app-footer">
                      ALGO LENS &nbsp; / &nbsp; Retrieval is not answer approval
                      &nbsp; / &nbsp; Verify every source before generation
                    </div>
                    """
                )

            with gr.Tab("Evidence"):
                with gr.Group(elem_classes=["surface"]):
                    gr.Markdown("### Evidence ledger")
                    gr.Markdown(
                        "Source passages and locators used for the latest request. "
                        "Unapproved passages are not presented as answer evidence.",
                        elem_classes=["section-help"],
                    )
                    evidence = gr.Markdown(
                        "Evidence will appear here after you submit a question.",
                        elem_classes=["evidence-output"],
                    )

            with gr.Tab("Trace"):
                with gr.Group(elem_classes=["surface"]):
                    gr.Markdown("### Claim verification")
                    gr.Markdown(
                        "Inspect the claims and request metadata returned by the answer service.",
                        elem_classes=["section-help"],
                    )
                    claims_report = gr.JSON(label="Claim report")
                    trace_report = gr.JSON(label="Request trace")

            with gr.Tab("Evaluation"):
                with gr.Group(elem_classes=["surface"]):
                    gr.Markdown(
                        """
                        ### Evaluation workspace

                        Unit and contract tests check software behavior; they do not,
                        by themselves, establish lecture-answer quality.

                        The current gold questions and answerability results remain
                        provisional. Before reporting benchmark performance, complete
                        human label review, freeze a development/test split, compare
                        retrieval baselines, run ablations, and report confidence
                        intervals.

                        Diagnostic report:
                        `eval/results/answerability_gate_diagnostic.json`
                        """
                    )

            with gr.Tab("About"):
                with gr.Group(elem_classes=["surface"]):
                    gr.Markdown(
                        """
                        ### Designed for traceable learning

                        - **Scope:** MIT 6.046J Lecture 6, Randomized Quicksort.
                        - **Grounding:** answers require approved evidence passages.
                        - **Abstention:** absent, ineligible, or unsupported evidence
                          should not become a confident answer.
                        - **Verification:** generated claims are checked against
                          retrieved passages before release.
                        - **Secrets:** API keys belong in local environment variables
                          or hosted Space Secrets and should never be shown in the UI.
                        """
                    )

        outputs = [answer, status, evidence, claims_report, trace_report]
        ask.click(
            answer_question,
            inputs=[question],
            outputs=outputs,
        )
        question.submit(
            answer_question,
            inputs=[question],
            outputs=outputs,
        )

    return demo


def readiness_payload() -> dict[str, Any]:
    """Report whether the app can safely generate grounded answers.

    Liveness is checked separately by /healthz. A running UI can be healthy
    while answer generation remains intentionally disabled in safe mode.
    """
    corpus = corpus_readiness()
    candidate_count = int(corpus.get("candidate_passages", 0))
    eligible_count = int(corpus.get("eligible_passages", 0))
    corpus_message = str(corpus.get("message", ""))

    if corpus_message.startswith("Corpus readiness could not be checked."):
        return {
            "status": "error",
            "ready": False,
            "answer_generation_enabled": False,
            "candidate_passages": candidate_count,
            "eligible_passages": eligible_count,
            "message": "The canonical corpus could not be checked.",
        }

    if eligible_count == 0:
        return {
            "status": "safe_mode",
            "ready": False,
            "answer_generation_enabled": False,
            "candidate_passages": candidate_count,
            "eligible_passages": 0,
            "message": (
                "The app is live, but no canonical passage has all required "
                "approval signals. Answer generation remains locked."
            ),
        }

    service, runtime_status = get_runtime()
    if service is None:
        return {
            "status": "runtime_unavailable",
            "ready": False,
            "answer_generation_enabled": False,
            "candidate_passages": candidate_count,
            "eligible_passages": eligible_count,
            "message": (
                "Approved passages exist, but the grounded-answer runtime "
                "could not be initialized."
            ),
            "runtime_status": str(runtime_status.get("message", "Runtime unavailable.")),
        }

    return {
        "status": "ready",
        "ready": True,
        "answer_generation_enabled": True,
        "candidate_passages": int(runtime_status.get("candidate_passages", candidate_count)),
        "eligible_passages": int(runtime_status.get("eligible_passages", eligible_count)),
        "message": "The grounded-answer runtime is initialized with approved evidence.",
    }


def create_server_app(blocks: gr.Blocks) -> FastAPI:
    """Mount the Gradio UI beside explicit liveness and readiness probes."""
    server = FastAPI(
        title="AlgoLens",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @server.get("/healthz", include_in_schema=False)
    def liveness_probe() -> dict[str, str]:
        """Return process liveness without depending on corpus/provider state."""
        return {"status": "ok", "service": "algolens"}

    @server.get("/readyz", include_in_schema=False)
    def readiness_probe() -> JSONResponse:
        """Return 200 only when the approved corpus and grounded runtime are ready."""
        report = readiness_payload()
        return JSONResponse(
            status_code=200 if report["ready"] is True else 503,
            content=report,
        )

    mount_kwargs: dict[str, Any] = {}
    if int(gr.__version__.split(".", maxsplit=1)[0]) >= 6:
        mount_kwargs["theme"] = APP_THEME
        mount_kwargs["css"] = APP_CSS

    return gr.mount_gradio_app(server, blocks, path="/", **mount_kwargs)


demo = create_app()
server_app = create_server_app(demo)


if __name__ == "__main__":
    is_space = bool(os.getenv("SPACE_ID"))
    host = os.getenv("GRADIO_SERVER_NAME", "0.0.0.0" if is_space else "127.0.0.1")
    port = int(os.getenv("PORT", "7860"))
    uvicorn.run(server_app, host=host, port=port, log_level="info")
