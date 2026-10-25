# Dense Retrieval

AlgoLens provides optional local dense retrieval using
`sentence-transformers/all-MiniLM-L6-v2`.

The model maps text to dense vectors. Documents and the query are embedded,
normalized, and ranked using cosine similarity. Embeddings are computed at
index initialization in this prototype; persistent embedding caching is a
future optimization.

The model can automatically select an available accelerator. Use `--device
cuda` to require CUDA or `--device cpu` to run on the CPU.

The default review policy is unchanged: the current chunks are unreviewed, so
no chunks are eligible for answer evidence. `--include-unreviewed` is a
diagnostic-only switch; it never changes a chunk's eligibility flag.

Dense scores are similarity scores, not calibrated probabilities or measures
of factual correctness. Evaluate retrieval on a labeled question set before
using it for answers.
