# Contributing

Thanks for helping improve repo-doctor!

## Ground rules

- **Zero runtime dependencies** — stdlib + git only. This is a core design goal.
- New checks belong in `repo_doctor/checks.py` and must return `Finding` (or a list), never raise on odd repo states.
- Every check needs a test in `tests/test_checks.py` (stdlib `unittest`, real temp git repos).

## Workflow

1. Fork and clone the repo.
2. `python -m unittest discover tests -v` should pass before and after your change.
3. Open a PR describing what the check catches and why the threshold is sane.

## Ideas for new checks

- Detect merge-commit-only history vs. squash/rebase conventions
- Warn on default branch not named `main`/`master`
- Detect vendored dependency directories committed to git
