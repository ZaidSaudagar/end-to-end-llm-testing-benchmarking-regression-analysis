# Documentation

Start with the full technical documentation. Everything else here supports it.

| Document | What it covers |
|---|---|
| [PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md) | **The main reference.** 20 chapters: architecture, modules, evaluation engine, provider layer, API reference, database schema, frontend, design system, datasets, configuration, setup, testing, security, limitations |
| [PROJECT_DOCUMENTATION.docx](PROJECT_DOCUMENTATION.docx) | The same document as a formatted Word file — 42 pages, 56 tables, embedded screenshots |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Condensed architecture overview across the seven platform layers |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Docker Compose release path, host preparation, public access, key rotation |
| [GITHUB_WORKFLOW.md](GITHUB_WORKFLOW.md) | Repository and CI conventions |

## Diagrams

Twelve Mermaid sources in [`diagrams/`](diagrams/). They render in any
Mermaid-compatible viewer — GitHub renders them inline, as do VS Code with the
Mermaid extension and <https://mermaid.live>.

| # | Diagram | Shows |
|---|---|---|
| 01 | [System architecture](diagrams/01-system-architecture.mmd) | Layers from UI to persistence |
| 02 | [Benchmark run sequence](diagrams/02-benchmark-run-sequence.mmd) | Request flow through a run |
| 03 | [Regression analysis flow](diagrams/03-regression-analysis-flow.mmd) | Statistical comparison pipeline |
| 04 | [Database schema](diagrams/04-database-schema.mmd) | Four tables and their relations |
| 05 | [Frontend component tree](diagrams/05-frontend-component-tree.mmd) | React component hierarchy |
| 06 | [Run lifecycle](diagrams/06-run-lifecycle.mmd) | Status transitions |
| 07 | [Provider retry and errors](diagrams/07-provider-retry-and-errors.mmd) | Backoff and error categorisation |
| 08 | [Request security pipeline](diagrams/08-request-security-pipeline.mmd) | Middleware and auth |
| 09 | [Dataset loading and scoring](diagrams/09-dataset-loading-and-scoring.mmd) | Validation, hashing, evaluation |
| 10 | [Deployment topology](diagrams/10-deployment-topology.mmd) | Containers and volumes |
| 11 | [Overview verdict derivation](diagrams/11-overview-verdict-derivation.mmd) | How the matrix verdict is computed |
| 12 | [Design system](diagrams/12-design-system.mmd) | Tokens and their roles |

## Screenshots

Seven captures in [`screenshots/`](screenshots/), taken from the running application
against live backend data — not mockups.

| File | View |
|---|---|
| [01-overview-desktop.png](screenshots/01-overview-desktop.png) | Overview at 1440px |
| [02-benchmark-studio.png](screenshots/02-benchmark-studio.png) | Run launcher |
| [03-dataset-explorer.png](screenshots/03-dataset-explorer.png) | Paginated case browser |
| [04-regression-matrix.png](screenshots/04-regression-matrix.png) | Two-run comparison |
| [05-model-studio.png](screenshots/05-model-studio.png) | Custom endpoint registry |
| [06-overview-mobile.png](screenshots/06-overview-mobile.png) | Overview at 390px |
| [07-run-detail-modal.png](screenshots/07-run-detail-modal.png) | Per-case inspection dialog |

## Regenerating the Word document

The `.docx` is generated from the Markdown, so the two cannot drift:

```bash
.venv\Scripts\python.exe docs\build_docx.py
```

Requires `python-docx`. The script parses the Markdown into blocks, renders real Word
tables with shaded headers, embeds the screenshots, and includes every Mermaid diagram
as a labelled code block. It also adds a cover page, a table-of-contents field, and a
page-number footer.
