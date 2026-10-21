# Architecture overview

The platform is designed around seven major layers:

1. Dataset management
2. Model provider adapters
3. Evaluation engine
4. Statistical analysis
5. Persistence
6. FastAPI backend
7. Streamlit dashboard

The current implementation includes dataset validation/fingerprinting and deterministic exact-match, numeric-tolerance, and JSON Schema checks under `backend/evaluation/`. `SemanticScorer` adds batch Sentence Transformers embeddings and cosine similarity, with injectable model loading for offline tests. `backend/providers/` contains Gemini and OpenRouter HTTP adapters, a normalized request/response contract, bounded retry behavior, optional cost-estimation injection, and a credential-free mock provider. The evaluation runner calls a configured provider sequentially for each dataset case, routes deterministic and semantic metrics separately, optionally runs the Milestone 5 judge, and persists a run and case results in SQLAlchemy tables. FastAPI exposes run creation and history endpoints. The analysis layer compares paired, completed case IDs across runs with the same dataset fingerprint, applies exact McNemar or Wilcoxon tests, bootstrap intervals, Holm-Bonferroni correction, and persists comparison reports. Dashboard presentation remains planned work.

Dataset files are treated as immutable inputs during loading: the loader validates their structure and records a SHA-256 digest of the exact source bytes in the returned dataset document. Test-case IDs are checked for uniqueness before any case can be evaluated. Unsupported methods, including reference-grounding and prompt-injection judgments, are rejected by the deterministic evaluator instead of being assigned a proxy score. Semantic proximity is stored separately and is never interpreted as factual correctness.

Provider adapters use provider-native REST payloads but return a shared response model with provider/model IDs, generated text, normalized token usage, latency, finish reason, request ID, and optional estimated cost. No pricing table is bundled. API keys are held in adapter instances and are never included in error messages or normalized results. Tests inject `httpx.MockTransport` to cover payloads and errors without network access.

Run creation accepts a dataset filename and restricts lookup to the repository's `datasets/` directory. The runner stores the exact source fingerprint, provider/model, aggregate usage/latency/cost when known, each candidate response, deterministic result or unsupported-method error, optional judge outcome, and sanitized provider error category. It commits one case at a time. Response text may contain sensitive data and is stored in the configured database; deployments should apply suitable access controls and retention rules.
