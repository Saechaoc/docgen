# Repository Guidelines

## Project Structure & Module Organization
- `spec/spec.md` captures the end-to-end architecture, component contracts, and must be updated whenever responsibilities shift.
- Place Python source in a `docgen/` package (create it when implementation starts) with clear submodules for orchestrator, analyzers, runners, and stores; avoid leaving logic in the repo root.
- Mirror runtime modules under `tests/` using `test_<module>.py`; co-locate fixtures in `tests/_fixtures/` so imports stay clean and reusable.
- Keep throwaway experiments inside an ignored `sandbox/` directory so repository scans remain focused on production code paths.

## Build, Test, and Development Commands
- `python -m venv .venv` followed by `.\\.venv\\Scripts\\activate` aligns local shells with the PyCharm interpreter settings.
- `python -m pip install -e .[dev]` (after a `pyproject.toml` is committed) exposes the CLI and plugins in editable form without repeated reinstalls.
- `python -m pytest` runs the full suite; append `-k <pattern>` to iterate on a single analyzer or pipeline stage.
- `python -m mypy docgen` and `python -m ruff check docgen tests` catch type drift and lint violations before README generation is attempted.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indents and explicit imports (for example, `from docgen.orchestrator import Pipeline`) so static tooling can trace dependencies.
- Name modules after their roles (`orchestrator.py`, `prompt_builder.py`) and keep functions snake_case with descriptive nouns first (`build_prompt_section`).
- Run `black docgen tests` before commits; avoid manual reformatting unless the formatter cannot resolve a construct.

## Testing Guidelines
- Pytest is the default harness; every analyzer or pipeline component needs unit coverage plus an integration case under `tests/integration/` that walks a repo snapshot through generation.
- Use descriptive test names such as `test_prompt_builder_handles_missing_signals` and keep Arrange-Act-Assert comments minimal but intentional.
- Store regression fixtures for generated README slices under `tests/data/` and update them with helper scripts so diffs stay reviewable.

## Commit & Pull Request Guidelines
- Follow Conventional Commits (`feat:`, `fix:`, `docs:`); keep subject lines <=72 characters and explain broader scope in the body when multiple subsystems change.
- Bundle related work into a single PR that includes a summary, testing notes, and links to relevant issues or spec sections; attach before/after README excerpts when altering generation output.
- Run lint, type-check, and test commands before opening a PR and paste condensed results in the description for quick verification.

## Environment & Tooling Notes
- Reuse the local `.venv` seeded by PyCharm; do not commit environment artifacts and store secrets in a `.env` consumed by the local LLM runner.
- Keep large model weights outside the repository and document their locations in `docs/models.md` once integration work begins.
