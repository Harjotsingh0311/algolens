from __future__ import annotations

import json

from algolens.nli_scorer import DEFAULT_NLI_MODEL_ID, NLIEntailmentScorer

EXAMPLES = [
    {
        "expected": "entailment",
        "premise": "A person is eating pizza.",
        "hypothesis": "A person is eating food.",
    },
    {
        "expected": "contradiction",
        "premise": "A person is asleep.",
        "hypothesis": "A person is awake.",
    },
    {
        "expected": "neutral",
        "premise": "A person is eating pizza.",
        "hypothesis": "A person lives in Paris.",
    },
]


def main() -> int:
    print(f"Loading actual NLI model: {DEFAULT_NLI_MODEL_ID}")
    print("The initial run may download model weights.")

    scorer = NLIEntailmentScorer()
    failures: list[str] = []

    for index, example in enumerate(EXAMPLES, start=1):
        scores = scorer(example["premise"], example["hypothesis"])
        predicted = max(scores, key=scores.__getitem__)
        expected = example["expected"]

        print(
            json.dumps(
                {
                    "example": index,
                    "expected": expected,
                    "predicted": predicted,
                    "scores": scores,
                },
                indent=2,
            )
        )

        if predicted != expected:
            failures.append(f"Example {index}: expected {expected}, got {predicted}")

    if failures:
        print("\nNLI SMOKE TEST NEEDS REVIEW:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("\nNLI SMOKE TEST PASSED.")
    print("Model loading, score shape, probability validation, and label mapping passed.")
    print("This is a smoke test, not a benchmark of factual accuracy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
