# Caption review packet

Generate a reproducible checklist for manually checking caption timestamps against the original lecture video:

```powershell
uv run python tools/create_caption_review_packet.py --count 10 --seed 2026
```

The default input is `corpus/raw/L06_CAPTIONS.en-qlPKC2UN_YU.vtt`; the default output is `eval/results/caption_timestamp_review.md`. Use `--input` and `--output` to override either path.

The sampling is deterministic for a fixed cue list, count, and seed. The generated packet includes the source caption text and timestamp, and blank fields for reviewer observations. Open the original video at each timestamp, listen, and record the observed words before marking a cue as matching.

**Important:** generating the packet does not perform the review. It must remain pending until a person checks the video. A successful timestamp review does not automatically approve chunks or enable retrieval; source transcription review and production eligibility are separate decisions.
