from __future__ import annotations

import argparse
import random
import re
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "corpus" / "raw" / "L06_CAPTIONS.en-qlPKC2UN_YU.vtt"
DEFAULT_OUTPUT = PROJECT_ROOT / "eval" / "results" / "caption_timestamp_review.md"
TIMESTAMP_RE = re.compile(
    r"(?m)^(\d{2}:\d{2}:\d{2}\.\d{3})\s+-->\s+"
    r"(\d{2}:\d{2}:\d{2}\.\d{3})(?:[^\r\n]*)$"
)


@dataclass(frozen=True)
class CaptionCue:
    start: str
    end: str
    text: str


def parse_cues(raw: str) -> list[CaptionCue]:
    """Parse non-empty WebVTT cues while preserving source timestamps."""
    matches = list(TIMESTAMP_RE.finditer(raw))
    cues: list[CaptionCue] = []
    for index, match in enumerate(matches):
        next_position = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        text = raw[match.end() : next_position]
        text = re.sub(r"<[^>]*>", " ", text)
        text = re.sub(r"&(?:amp|lt|gt|nbsp);", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            cues.append(CaptionCue(match.group(1), match.group(2), text))
    return cues


def build_review_packet(
    cues: list[CaptionCue], *, count: int = 10, seed: int = 2026
) -> str:
    """Create a reproducible manual-review checklist; never imply cues are verified."""
    if count < 1:
        raise ValueError("count must be at least 1.")
    if not cues:
        raise ValueError("No non-empty caption cues were found.")
    if count > len(cues):
        raise ValueError(f"Requested {count} samples but only {len(cues)} non-empty cues exist.")

    selected = sorted(random.Random(seed).sample(cues, count), key=lambda cue: cue.start)
    lines = [
        "# Caption-to-video timestamp review",
        "",
        "**Status: PENDING HUMAN REVIEW.** This packet samples caption cues; it does not verify",
        "that the words or timestamps match the lecture video and does not approve the corpus.",
        "",
        f"- Sampling seed: `{seed}`",
        f"- Requested/selected samples: {count}",
        "- Reviewer: ____________________",
        "- Review date (YYYY-MM-DD): ____________________",
        "",
        "For each row, open the original lecture video at the timestamp, listen to the spoken",
        "content, and record what you actually hear. Mark match only after checking the video.",
        "",
        "| # | Caption timestamp | Caption text from VTT | Matches video? | Observed words / notes |",
        "|---:|---|---|---|---|",
    ]
    for index, cue in enumerate(selected, start=1):
        safe_text = cue.text.replace("|", "\\|")
        lines.append(
            f"| {index} | {cue.start}–{cue.end} | {safe_text} | Pending | ____________________ |"
        )
    lines.extend(
        [
            "",
            "## Reviewer conclusion",
            "",
            "- [ ] All sampled cues checked against the original video.",
            "- [ ] Mismatches recorded above and corrected in a separate reviewed artifact.",
            "- [ ] Any correction has been checked against the source and reviewed by a human.",
            "",
            "**Do not change canonical passage eligibility from this checklist alone.**",
            "Timestamp/text review and production retrieval eligibility are separate decisions.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a reproducible manual caption-to-video review checklist."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Input WebVTT file.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output Markdown path.")
    parser.add_argument("--count", type=int, default=10, help="Number of cues to sample.")
    parser.add_argument("--seed", type=int, default=2026, help="Sampling seed.")
    args = parser.parse_args()

    if not args.input.is_file():
        raise SystemExit(f"Caption file not found: {args.input}")
    raw = args.input.read_text(encoding="utf-8-sig")
    if not raw.startswith("WEBVTT"):
        raise SystemExit("Input does not start with WEBVTT.")

    cues = parse_cues(raw)
    packet = build_review_packet(cues, count=args.count, seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(packet, encoding="utf-8")
    print(f"Wrote {args.count} pending human-review rows to {args.output}")
    print("No captions or corpus approval flags were changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
