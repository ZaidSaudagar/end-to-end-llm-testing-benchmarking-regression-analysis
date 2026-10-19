# End-to-End LLM Testing, Benchmarking and Regression Analysis

A portfolio-grade platform for benchmarking large language models, measuring deterministic and semantic quality, detecting regressions, and comparing model behavior across providers.

## Overview

This project is designed around a modular architecture that separates:

- dataset management and validation
- provider adapters for Gemini and OpenRouter
- evaluation logic for correctness, semantic similarity, and reliability checks
- statistical comparison and regression analysis
- persistent run history
- a professional Streamlit dashboard

The repository is intentionally structured so the underlying evaluation engine is independent from the UI and can be used from Python and the FastAPI backend.

## Current milestone

This repository is at Milestone 1: foundation and GitHub setup.

The initial implementation includes project scaffolding, configuration, server startup, a minimal database foundation, and a starter dashboard. The next milestone will add dataset validation and deterministic evaluation logic.

## Architecture

```text
User / operator
      |
      v
Streamlit dashboard
      |
      v
FastAPI backend
      |
      +--> Evaluation engine
      +--> Dataset validation
      +--> Provider adapters
      +--> SQLite persistence
      +--> Run history / reporting
```

## Tech stack

- Python 3.11+
- FastAPI
- Streamlit
- SQLAlchemy + SQLite
- Pydantic
- Plotly
- HTTPX
- pytest
- Ruff
- GitHub Actions

## Local setup

```bash
cd "D:\Projects\End-to-End-LLM-Testing-Benchmarking-and-Regression-Analysis"
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install fastapi uvicorn streamlit sqlalchemy httpx python-dotenv pydantic pytest ruff plotly pandas numpy scikit-learn sentence-transformers scipy
```

## Run the app

Backend:

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Dashboard:

```bash
streamlit run dashboard/app.py --server.headless true --server.port 8501
```

## Project structure

```text
.
├── backend/
│   ├── __init__.py
│   ├── config.py
│   ├── database.py
│   ├── main.py
│   └── models/
├── dashboard/
│   └── app.py
├── datasets/
│   └── README.md
├── docs/
│   ├── ARCHITECTURE.md
│   └── GITHUB_WORKFLOW.md
├── tests/
│   └── test_health.py
├── .env.example
├── .gitignore
├── CONTRIBUTING.md
├── pyproject.toml
└── README.md
```

## Testing

```bash
pytest -q
```

## Environment and secrets

Use `.env` locally for environment variables. Do not commit secrets or real API keys. The repository includes `.env.example` as the safe template.

## Roadmap

- Milestone 1: foundation and GitHub setup
- Milestone 2: dataset and evaluation core
- Milestone 3: semantic NLP evaluation
- Milestone 4: provider integration
- Milestone 5: LLM-as-a-judge
- Milestone 6: evaluation execution and persistence
- Milestone 7: statistics and regression analysis
- Milestone 8: dashboard completion
- Milestone 9: reliability and security hardening
- Milestone 10: release packaging and deployment

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contributor guidance and repository workflow expectations.