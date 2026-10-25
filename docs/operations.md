# AlgoLens operational probes

## HTTP endpoints

| Endpoint | Meaning | Expected current result |
|---|---|---|
| GET /healthz | Liveness only; confirms the web process can answer HTTP requests. Does not initialize models or inspect the corpus. | 200, status "ok" |
| GET /readyz | Strict answer-generation readiness; checks canonical evidence eligibility and initializes the grounded runtime when eligible evidence exists. | Currently 503 with status "safe_mode", because no canonical passage has all required approval signals. |

A /readyz 503 does not mean the UI process has crashed. It means generation is deliberately not available. Use /healthz for liveness; use /readyz only for readiness to produce grounded answers.

The endpoints expose counts and a sanitized status message only. They do not return filesystem paths, prompts, API keys, request headers, or raw provider exceptions.

## Local verification (PowerShell)

Run the app:

    Set-Location -LiteralPath 'C:\workstation\3RD YEAR\rag_for_submit'
    uv run python app/app.py

In a second PowerShell terminal, check liveness:

    Invoke-RestMethod 'http://127.0.0.1:7860/healthz'

Check generation readiness. In the current safe-mode state, a 503 is expected:

    try {
        Invoke-WebRequest 'http://127.0.0.1:7860/readyz' -SkipHttpErrorCheck |
            Select-Object StatusCode, Content
    } catch {
        Write-Host $_.Exception.Message
    }

Do not change approval flags just to make /readyz return 200. Readiness should become 200 only after a genuine source review, an explicit retrieval-eligibility decision, and successful runtime initialization.

## Deployment note

Both routes are served by the same FastAPI/Gradio process, using the configured PORT environment variable. These are probes only; no Hugging Face Space has been deployed from this checkpoint.
