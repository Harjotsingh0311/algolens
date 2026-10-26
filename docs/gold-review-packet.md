# Gold-question human review packet

Generate a Markdown review packet from the 80-question candidate and diagnostic child chunks:

```powershell
uv run python -m algolens.evaluation.review_packet
```

The default output is `eval/results/gold_review_packet.md`. Use `--root` when running outside the checkout, or `--output` to select another destination.

For every candidate question, the packet includes the question, candidate answerability label, key points, passage IDs, available diagnostic text, source/citation metadata, and a human-review checklist. It explicitly labels diagnostic-only passages as unapproved evidence. Empty passage lists are surfaced for review rather than automatically treated as errors, because some unanswerable questions may correctly have no gold passage IDs.

The packet is a review aid only. It does not modify the candidate JSONL, canonical chunks, or approval flags, and it does not authorize final evaluation. Review evidence against the original lecture and canonical corpus before any separate approval workflow.
