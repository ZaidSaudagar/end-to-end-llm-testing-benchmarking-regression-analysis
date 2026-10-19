# GitHub workflow guidance

- Initialize Git in the project directory.
- Add a clean `.gitignore` before committing any generated files.
- Use conventional commit messages.
- Keep CI secret-free and avoid real API keys in tests.
- Run `pytest` and `ruff` in CI.