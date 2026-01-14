# Repository Guidelines

## Project Structure & Module Organization
- `spider/` holds the runtime code. The main entry point is `spider/spider.py`.
- `pyproject.toml` defines dependencies and Python requirements; `uv.lock` pins versions.
- `README.md` is present but currently empty; keep high-level usage notes there if expanded later.

## Build, Test, and Development Commands
- `uv sync` installs pinned dependencies from `uv.lock` into the active environment.
- `uv run python spider/spider.py` runs the live downloader with the current project dependencies.
- If you are not using `uv`, install via `python -m pip install -e .` and run `python spider/spider.py`.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation and snake_case for functions and variables.
- Keep utility helpers small and pure (for example, filename sanitization helpers).
- Prefer explicit names for network responses (`live_response`, `room_info`) over single letters.

## Testing Guidelines
- No test suite is currently included; add `tests/` if you introduce reusable modules.
- If you add tests later, use `pytest` and name files `test_*.py`.

## Commit & Pull Request Guidelines
- There is no Git history yet, so no established commit conventions exist. Use short, imperative messages (e.g., "Add live segment downloader").
- PRs should include a concise description, manual run steps, and any configuration changes.

## Security & Configuration Tips
- `spider/spider.py` uses authenticated cookies (notably `SESSDATA`). Do not commit real credentials; prefer environment variables or a local, gitignored config file.
- The script writes to local folders (e.g., `temp/<room_id>` and `<uname>/`), so confirm output paths before long runs.
