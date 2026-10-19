# Contributing

## Workflow

1. Create a feature branch.
2. Keep work scoped to the active milestone.
3. Run targeted tests locally before requesting review.
4. Keep secrets out of the repository.
5. Update docs when the implementation changes.

## Local development

```bash
cd "D:\Projects\End to End LLM Testing Benchmarking and Regression Analysis"
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

For this project, dependencies are managed in `pyproject.toml` and installed with pip.
