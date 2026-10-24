# Experimental PDF Extraction Outputs

These files are comparison artifacts created during source-ingestion development.
They are **not approved canonical lecture content** and must not be ingested
automatically as trusted sources.

## Files

- `notes.md`: PyMuPDF4LLM Markdown extraction.
- `notes_docling_cuda.md`: Docling with the CUDA accelerator configured.
- `notes_docling_cuda_torch_ocr.md`: Docling using its Torch OCR backend.

## Known limitations

Formula formatting is damaged in examples involving probabilities and pivot
bounds. The Docling runs had the same reported character, line, and candidate
counts, but these counts do not establish mathematical accuracy.

Use the original PDF and `docs/extraction-evaluation.md` for provenance and
evaluation findings. The separate formula-review reference covers selected
equations only; it is not a full validation of the lecture.
