import hashlib
import re
from pathlib import Path

project = Path(__file__).resolve().parents[1]
caption_path = (
    project
    / "corpus"
    / "raw"
    / "L06_CAPTIONS.en-qlPKC2UN_YU.vtt"
)

if not caption_path.is_file():
    raise SystemExit(f"FAIL: Caption file not found: {caption_path}")

raw = caption_path.read_text(encoding="utf-8-sig")

if not raw.startswith("WEBVTT"):
    raise SystemExit("FAIL: File does not start with WEBVTT.")

pattern = re.compile(
    r"(?m)^(\d{2}:\d{2}:\d{2}\.\d{3})\s+-->\s+"
    r"(\d{2}:\d{2}:\d{2}\.\d{3})(?:[^\r\n]*)$"
)
matches = list(pattern.finditer(raw))

if not matches:
    raise SystemExit("FAIL: No timestamp cues found.")

def seconds(value: str) -> float:
    hours, minutes, remainder = value.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(remainder)

issues: list[str] = []
max_gap = 0.0
previous_start = -1.0
previous_end = 0.0
all_text: list[str] = []

for i, match in enumerate(matches):
    start = seconds(match.group(1))
    end = seconds(match.group(2))

    if start >= end:
        issues.append(f"Cue {i + 1}: start is not before end.")

    if start < previous_start:
        issues.append(f"Cue {i + 1}: start timestamp moves backwards.")

    if i and start > previous_end:
        max_gap = max(max_gap, start - previous_end)

    next_position = (
        matches[i + 1].start() if i + 1 < len(matches) else len(raw)
    )
    cue_text = raw[match.end():next_position]
    cue_text = re.sub(r"<[^>]*>", " ", cue_text)
    cue_text = re.sub(r"&(?:amp|lt|gt|nbsp);", " ", cue_text)
    cue_text = re.sub(r"\s+", " ", cue_text).strip()

    if cue_text:
        all_text.append(cue_text)

    previous_start = start
    previous_end = max(previous_end, end)

full_text = " ".join(all_text)
lower_text = full_text.lower()
word_count = len(re.findall(r"\b[\w'-]+\b", full_text))
digest = hashlib.sha256(caption_path.read_bytes()).hexdigest()

print("========== CAPTION AUDIT ==========")
print(f"File: {caption_path.name}")
print(f"Size: {caption_path.stat().st_size:,} bytes")
print(f"Timestamp cues: {len(matches):,}")
print(f"Approximate word count: {word_count:,}")
print(f"First cue: {matches[0].group(1)} -> {matches[0].group(2)}")
print(f"Last cue: {matches[-1].group(1)} -> {matches[-1].group(2)}")
print(f"Largest gap between consecutive cues: {max_gap:.3f} seconds")
print(f"Timestamp issues: {len(issues)}")

for issue in issues[:10]:
    print("TIMING ISSUE:", issue)

print("\n========== TOPIC COVERAGE ==========")
for term in (
    "quicksort",
    "quick sort",
    "randomized",
    "pivot",
    "partition",
    "expected time",
    "matrix multiply",
):
    print(f"{term}: {lower_text.count(term)}")

print("\n========== FIRST CAPTION TEXT ==========")
print(full_text[:1000])

print("\n========== SHA-256 ==========")
print(digest)

if issues:
    print("\nAUDIT RESULT: REVIEW REQUIRED")
else:
    print("\nAUDIT RESULT: TIMESTAMP ORDER CHECK PASSED")

if max_gap > 30:
    print("WARNING: At least one inter-cue gap exceeds 30 seconds.")