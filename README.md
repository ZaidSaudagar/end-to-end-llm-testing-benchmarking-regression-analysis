# End-to-End LLM Testing, Benchmarking and Regression Analysis

A portfolio-grade platform for benchmarking large language models, measuring deterministic and semantic quality, detecting regressions, and comparing model behavior across providers.

## Overview

This project is designed around a modular architecture that separates:

- dataset management, inspection, and validation
- provider adapters for Groq, Google Gemini, KiraAI MiniMax, and dynamic custom LLMs
- evaluation logic for correctness, semantic similarity, and reliability checks
- statistical comparison and regression analysis (Wilcoxon, McNemar)
- persistent run history in SQLite
- a modern high-performance React + TypeScript web dashboard

The repository is intentionally structured so the underlying evaluation engine is independent from the UI and can be used from Python and the FastAPI backend.

**Full technical documentation:** [docs/PROJECT_DOCUMENTATION.md](docs/PROJECT_DOCUMENTATION.md) — architecture, modules, API reference, database schema, design system, and testing. A Word version is at [docs/PROJECT_DOCUMENTATION.docx](docs/PROJECT_DOCUMENTATION.docx), 12 Mermaid diagrams live in [docs/diagrams/](docs/diagrams/), and [docs/README.md](docs/README.md) indexes the whole folder.

## Current milestone

Milestones 1–10 are implemented in the current local checkout. The platform validates the supplied CSV and JSON datasets, rejects duplicate case IDs, records a SHA-256 fingerprint for each source file, and supports deterministic exact-match, numeric-tolerance, and JSON Schema checks. Sentence Transformers semantic similarity is available as a separate batch metric. Groq, Gemini, and MiniMax-compatible adapters normalize text, token usage, latency, finish reason, and request identifiers. An optional rubric-based LLM judge returns validated dimension scores and rationales, tracks judge/prompt/rubric versions and usage, supports bounded malformed-response repair and repeated scoring, and records failures without substituting zero. The FastAPI backend executes datasets, persists runs, and exposes run history and paired regression analysis. A modern React + TypeScript dashboard provides live execution, side-by-side regression diffs, dataset inspection, and custom model registration. Production configuration adds API-key protection and database readiness checks; Docker Compose packages the backend and frontend for deployment.

The supplied datasets are project fixtures, not externally validated or statistically representative benchmarks. See [datasets/README.md](datasets/README.md) for their schema and limitations. Results should be interpreted alongside paired case outputs and uncertainty estimates, not as universal model rankings.

## Architecture

```text
User / operator
      |
      v
Modern Web Dashboard (React + TypeScript + Vite)
      |
      v
FastAPI backend
      |
      +--> Evaluation engine (deterministic, semantic, and judge checks)
      +--> Dataset validation, inspection, and hashing
      +--> Provider adapters (Groq, Gemini, KiraAI MiniMax, Custom OpenAI endpoints)
      +--> SQLite persistence
      +--> Statistical regression analysis & run history
```

## Tech stack

- Python 3.11+
- FastAPI
- React 19 + Vite 8 + TypeScript
- SQLAlchemy + SQLite
- Pydantic
- HTTPX
- pytest
- Ruff
- oxlint
- GitHub Actions
- Docker and Docker Compose

## Local setup

```bash
cd "D:\Projects\End to End LLM Testing Benchmarking and Regression Analysis"
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

## Run the app

Backend:

```bash
uvicorn backend.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Project structure

```text
.
├── backend/
│   ├── evaluation/       # Evaluation engine, metrics, semantic, runner, analysis
│   ├── providers/        # Groq, Gemini, MiniMax, Custom OpenAI adapters
│   ├── config.py         # App configuration & settings
│   ├── database.py       # SQLAlchemy setup
│   ├── main.py           # FastAPI REST endpoints
│   └── models.py         # Database ORM models
├── datasets/             # Test cases (CSV/JSON) and manifest
├── docs/                 # Documentation, diagrams, and screenshots
│   ├── README.md                   Index of everything in this folder
│   ├── PROJECT_DOCUMENTATION.md    Full technical documentation
│   ├── PROJECT_DOCUMENTATION.docx  Word version
│   ├── ARCHITECTURE.md             Condensed architecture overview
│   ├── DEPLOYMENT.md               Docker Compose release path
│   ├── build_docx.py               Regenerates the .docx from the .md
│   ├── diagrams/                   12 Mermaid diagram sources
│   └── screenshots/                Captured from the running app
├── frontend/             # React 19 + Vite 8 + TypeScript dashboard
│   └── README.md                   Frontend-specific setup and structure
├── tests/                # Automated pytest test suites
├── .github/workflows/    # CI: pytest, ruff, tsc, oxlint, vite build, docker build
├── Dockerfile
├── compose.yaml
├── pyproject.toml
└── README.md
```

## Testing

```bash
pytest -q
```

Current result: **54 passed, 1 skipped**. The skipped test requires local `sentence-transformers` model weights.

Frontend checks:

```bash
cd frontend
npx tsc -b --noEmit    # type-check
npm run lint           # oxlint
npm run build          # production build
```

## Regenerating the documentation

The Word document is generated from the Markdown source, so the two never drift:

```bash
.venv\Scripts\python.exe docs\build_docx.py
```

This produces `docs/PROJECT_DOCUMENTATION.docx` with real Word tables, styled headings, a table-of-contents field, embedded screenshots, and every Mermaid diagram source. It requires `python-docx` (`pip install python-docx`).

## Supplied datasets

The `datasets/` directory contains the Benchmark Dataset Pack v1.0.0: 63 general benchmark cases and 20 cases each for structured output, reference grounding, and controlled prompt injection. `manifest.json` records SHA-256 hashes for the supplied files. The loader recalculates a hash from each dataset's exact bytes and validates IDs and required fields before the cases can be used.

These are project-specific starter fixtures, not an externally validated or statistically representative benchmark. Results must not be presented as universal model rankings. Semantic similarity is reported separately from correctness. See [datasets/README.md](datasets/README.md) for the dataset schema and limitations.

## Semantic similarity

The default embedding model is `sentence-transformers/all-MiniLM-L6-v2`, pinned to revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. Override `EMBEDDING_MODEL_ID` and `EMBEDDING_MODEL_REVISION` in `.env` to select a different compatible Sentence Transformers model/revision. The first real scoring call loads the model and caches it for the process. `SemanticScorer.score_batch()` accepts aligned reference/candidate text and returns cosine similarity with the model ID, revision, and Sentence Transformers library version. Missing references or candidates receive a missing score (`null`), not zero.

Automated unit tests use a fake encoder and do not download model weights. To run the opt-in real-model smoke test on a machine with model access, set `RUN_REAL_EMBEDDING_TESTS=1` and run `pytest tests/test_semantic_integration.py -q`. Its synthetic paraphrase fixture checks that a paraphrase scores above an unrelated sentence; it is not a benchmark result.

## Model providers

Provider requests are asynchronous and can be called from Python. `GeminiProvider` uses Google's `generateContent` REST method; `MiniMaxProvider` uses the OpenAI-compatible chat completion API. MiniMax settings are `MINIMAX_API_KEY`, `MINIMAX_BASE_URL`, and `MINIMAX_MODEL` (or `MINIMAX_MODEL_ID`); the Kira AI endpoint and `kira-3.5-flash` model are configured in the local `.env`. The Gemini model ID can be changed with `GEMINI_MODEL_ID`; pass a request-level `model_id` to override one request. The factory returns adapters for configured credentials only.

The adapters apply bounded timeouts and retries for timeouts, transport failures, HTTP 408/429, and server errors. Retried generation requests can be received more than once by a provider. Authentication and other client errors are not retried. Errors are normalized without including API keys or provider response bodies. Token counts and latency are normalized; estimated cost remains `null` unless a model-specific `CostEstimator` is supplied, so the project does not invent pricing.

All provider tests use `httpx.MockTransport` or `MockProvider`; they do not require API keys or send paid requests. The provider-backed run API is available in FastAPI and the dashboard can start and inspect runs.
## Evaluation runs

Run creation uses only files inside `datasets/`; callers provide a filename rather than an arbitrary filesystem path. Each run stores the dataset name, version and SHA-256, provider/model, status, token counts, latency, and any available estimated cost. Each case stores the candidate text, normalized provider metadata, deterministic result, semantic similarity result, optional judge outcome, evaluation error, or sanitized provider failure category. Results are committed as cases finish so a later provider failure does not erase earlier progress. Cases marked `semantic_similarity` load the configured embedding model on first use; see the semantic scoring section. Generated responses are persisted in the local database, so use care with datasets that contain private or sensitive inputs.

Configure a provider key in `.env`, start the backend, then create and inspect a run:

```bash
curl -X POST http://127.0.0.1:8000/api/runs \
  -H "Content-Type: application/json" \
  -d '{"dataset_file":"benchmark_dataset.csv","provider":"minimax"}'

curl http://127.0.0.1:8000/api/runs
curl http://127.0.0.1:8000/api/runs/<run-id>
```

Add `"model_id":"provider/model-name"` to override the provider default. Add `"include_judge":true` to enable the optional judge for this run; judging must also be enabled in `.env` and its provider key configured. Calls are sequential in this milestone. Unsupported evaluation methods are recorded as evaluation errors instead of being assigned proxy scores. Provider errors are retained per case and the run continues with the next case.

## Statistics and regression analysis

Compare two saved runs using `POST /api/analyses/compare` with `baseline_run_id` and `candidate_run_id`. The runs must have the same dataset SHA-256, and only case IDs completed in both runs contribute. The report includes paired means and deltas for deterministic pass rate, semantic similarity, judge overall score, and available judge dimensions. Binary pass-rate changes use an exact McNemar test; continuous scores use a Wilcoxon signed-rank test. Paired bootstrap intervals summarize uncertainty in the mean delta, and Holm-Bonferroni adjustment controls the family-wise error rate across reported metrics. A regression is flagged only when the adjusted p-value is below `alpha` and the candidate mean drop exceeds `minimum_regression_drop`.

The API defaults to `alpha=0.05` and `minimum_regression_drop=0`. The minimum drop uses the metric's own scale: pass rate is a fraction (0.05 means five percentage points), semantic similarity is cosine similarity, and judge scores use the 1–5 rubric scale. Analyses are persisted and can be listed with `GET /api/analyses` or retrieved with `GET /api/analyses/{analysis_id}`.

## Dashboard

The React dashboard has five sections, all reading live data from the FastAPI backend.

**Overview** opens on the regression matrix — pass rate per model, latest run against the previous run of the same model, with the delta and a regression verdict. A plain-language verdict line sits above it, and a dense run ledger follows below. The matrix is the first thing in the viewport because a regression is the most important thing the platform can tell you.

**Benchmark Studio** selects a dataset, a configured provider, a model, and whether to run the judge, then launches a run. Provider and model lists come from `GET /api/config/providers`, so only providers with a key configured are selectable.

**Dataset Explorer** browses the cases in any dataset with search, category and difficulty filters, paginated 25 cases per page.

**Regression Matrix** compares any two completed runs of the same dataset, with adjustable `alpha` and minimum regression drop.

**Model & Provider Studio** registers and tests any OpenAI-compatible endpoint — local Ollama, LM Studio, vLLM, or a hosted gateway — and lists built-in provider status.

Clicking any run opens a per-case inspection dialog with a status filter. The dialog traps focus, closes on Escape, and returns focus to the row that opened it.

The interface is responsive down to 390px. Below 768px the regression matrix scrolls horizontally inside its own container with the model column pinned, and ledger rows collapse to two lines rather than stacking into cards.

Configure the backend address with `VITE_BACKEND_URL` when it is not `http://127.0.0.1:8000`.

### Design system

The visual language follows one rule: **rose (`#f43f5e`) means regression, and nothing else.** Every other status is rendered in neutral greys and distinguished by its label rather than by colour. There are no gradients, no glassmorphism, and no shadows — depth comes from a one-step surface lift plus a hairline border. Typography is IBM Plex Sans for UI and IBM Plex Mono for identifiers and metric values, in sentence case throughout. A global `prefers-reduced-motion` block disables animation, and every interactive element has a visible `:focus-visible` ring. See [section 12 of the documentation](docs/PROJECT_DOCUMENTATION.md#12-design-system).

## Security and deployment

For local development, API-key protection is optional. In production, set `ENVIRONMENT=production`, `DEBUG=false`, a `BACKEND_API_KEY` with at least 32 characters, explicit `CORS_ORIGINS`, and explicit `ALLOWED_HOSTS`. The frontend sends `VITE_BACKEND_API_KEY` as `X-API-Key` when it is set. Production disables interactive API documentation; `/ready` checks the database connection. Request bodies are limited to 1 MiB.

Build and run the single-host Docker Compose deployment with persistent SQLite and model-cache volumes by following [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). It binds the backend port to loopback by default, requires an API key, and runs the application as a non-root user. SQLite is a single-backend-instance deployment. Put a TLS reverse proxy with user authentication in front of the frontend before enabling remote access; the backend API key does not authenticate frontend users. CI builds the deployment image but does not publish or deploy it.

```bash
curl -X POST http://127.0.0.1:8000/api/analyses/compare \
  -H "Content-Type: application/json" \
  -d '{"baseline_run_id":"<baseline-run-id>","candidate_run_id":"<candidate-run-id>","alpha":0.05}'
```

Regression flags are statistical signals, not proof that a model caused a change. Small or project-authored datasets have limited power and representativeness. Review paired case counts, effect sizes, intervals, failure rates, and qualitative outputs before drawing conclusions. Partial runs compare only the cases with usable values in both runs; a one-pair result is descriptive and has no significance test.

## LLM-as-a-judge

Judging is disabled by default. To enable it, set `JUDGE_ENABLED=true`, choose a configured `JUDGE_PROVIDER` (`gemini` or `minimax`), and set `JUDGE_MODEL_ID`. The provider's corresponding API key must be configured. `JUDGE_MAX_RESPONSE_ATTEMPTS` is bounded to 1–3 and `JUDGE_REPETITIONS` to 1–5. Each repetition is a separate provider request and may incur cost; judge output includes provider/model, prompt and rubric versions, token usage, latency, and any available estimated cost. No calls are made when judging is disabled.

The versioned rubric scores relevance, completeness, instruction following, factual alignment with supplied references, and clarity from 1–5. When no reference answer or context is supplied, factual alignment is explicitly not assessed and excluded from the overall mean. Candidate model identity is retained as run attribution but omitted from the judge prompt to reduce direct identity bias. Each judge response must be JSON that passes a strict schema; after bounded repair attempts, the run stores a failure category and no scorecard. Repeated runs aggregate successful scores only, report failures separately, and provide a population standard deviation when at least two repetitions succeed.

LLM judges are imperfect: scores can vary with wording, position, model choice, and judge preferences; concise rationales are not proof of correctness. Blinding candidate identity does not eliminate bias, and candidate content can still contain adversarial instructions. Treat these scores as one evaluation signal, compare them with deterministic metrics and human review, and periodically audit agreement and stability. See [Judging the Judges: A Systematic Study of Position Bias in LLM-as-a-Judge](https://aclanthology.org/2025.ijcnlp-long.18/).

Example usage from Python:

```python
from backend.evaluation import JudgeRequest, build_configured_judge

judge = build_configured_judge()
if judge is not None:
    outcome = await judge.evaluate(
        JudgeRequest(
            prompt="Explain the result in one sentence.",
            candidate_answer="The result is 42.",
            reference_answer="The answer to life is 42.",
            test_case_id="case-001",
            candidate_model_id="candidate-model-a",
        )
    )
    print(outcome.status, outcome.aggregate)
```

Example dataset validation from Python:

```python
from backend.evaluation import load_dataset

dataset = load_dataset("datasets/benchmark_dataset.csv")
print(dataset.dataset_name, dataset.dataset_version, len(dataset.cases))
print(dataset.source_sha256)
```

## Environment and secrets

Use a private `.env` file in the project root for environment variables. Add your MiniMax key as `MINIMAX_API_KEY` before starting evaluations. Do not commit `.env` or share its contents; it is excluded from Git.
