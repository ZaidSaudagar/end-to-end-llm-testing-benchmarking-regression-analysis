# Benchmark Dataset Pack

Dataset version: 1.0.0
Created: 2026-10-19

These are project-specific starter evaluation datasets authored for the
End-to-End LLM Testing, Benchmarking and Regression Analysis project.
They are not an externally validated or standardized benchmark.

## Files

- `benchmark_dataset.csv` — 63 general benchmark cases across factual QA, arithmetic, programming, summarization, reasoning, instruction following, data interpretation, NLP, uncertainty and statistics.
- `structured_output_tests.json` — 20 JSON/schema-oriented test cases.
- `reference_grounding_tests.json` — 20 tests for reference-supported answers and appropriate abstention when information is missing.
- `prompt_injection_tests.json` — 20 controlled prompt-injection robustness cases.

## Important limitations

1. These datasets are initial project-specific fixtures, not a statistically representative benchmark of all LLM use cases.
2. Reference answers and expected behaviors should be reviewed and versioned before using scores for public model rankings.
3. Semantic similarity does not prove factual correctness. The project's embedding score is an independent cosine-similarity signal, not a correctness probability.
4. Prompt-injection tests are controlled examples and do not establish comprehensive security.
5. Cost and latency depend on provider, model, region, request settings and network conditions.
6. Do not present results from these cases as universal model rankings.

## CSV schema

`test_case_id`, `task_category`, `input_prompt`, `reference_answer`,
`evaluation_method`, `difficulty`, `reference_context`,
`expected_output_schema`, `dataset_version`, `tags`

## JSON conventions

Each JSON file has a top-level `dataset_name`, `dataset_version`,
`description`, and `cases` array. Each case has a stable `test_case_id`.
Schema expectations are represented as JSON Schema-like objects; use a JSON
Schema validator if the implementation supports the relevant keywords.

## Integration note

Antigravity should validate these fields against the project's implemented
Pydantic schemas. If the code's schema differs, adapt the dataset through a
versioned conversion script rather than silently dropping fields.
