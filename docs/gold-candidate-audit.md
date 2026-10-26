# Gold candidate audit

Run this read-only audit before attempting final evaluation:

```powershell
uv run python -m algolens.evaluation.gold_audit
```

The command writes `eval/results/gold_candidate_audit.json` and prints the same report. Use `--root` when running outside the checkout, or `--output` to choose a report path.

It checks the candidate question count, question-type distribution, proposed 50/30 split, duplicate IDs, required fields, and every referenced passage ID against both:
- `corpus/processed/reviewed_chunks/children.jsonl` (canonical reviewed corpus)
- `corpus/experiments/chunking/children.jsonl` (diagnostic-only corpus)

A passage found only in the diagnostic corpus is **not** production evidence. The audit never edits the candidate questions, approves a label, changes a chunk, or enables answer generation. Human source review and explicit canonical passage approval remain required; a structurally clean report does not mean the gold set is ready for final evaluation.
