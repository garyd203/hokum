# hokum - project notes

hokum is a CLI tool that adapts ordinary CLI commands to the Claude Code hook
protocol. Python, Poetry-managed, `src/` layout, published to PyPI.

## Release pipeline: fragile name bindings

These names are load-bearing. Renaming any of them breaks releases *silently* -
no error, releases just stop happening:

* `.github/workflows/manual-release.yml` - the PyPI trusted publisher is
  registered against this exact filename. Rename only in lockstep with the
  publisher config on PyPI.
* The `pypi` GitHub environment - also part of the PyPI trusted publisher
  registration, and its settings (deployment branch rule = `main`, required
  reviewer) are the *only* branch restriction and manual gate for releases.
* The `Code Checks` workflow display name (the `name:` field in
  `code-checks.yml`) - the release workflow's `workflow_run` trigger matches
  on it.

## How releases happen

1. Bump the version and update `CHANGELOG.md`, merge to `main`.
2. A green "Code Checks" run on `main` triggers the Release workflow, which
   releases iff the version isn't already on PyPI (otherwise it's a green
   no-op).
3. The `publish` job pauses at the `pypi` environment for manual approval -
   that approval is the release button.
4. After publishing, the workflow smoke-tests the package from PyPI and pushes
   the `v{version}` git tag. Never tag releases manually.

## Version management

* Bump with `bump-my-version bump patch|minor|major` (no commit/tag - config
  is in `pyproject.toml`).
* Source of truth is `src/hokum/__about__.py`; `pyproject.toml` is rewritten
  to match.
* The release workflow parses the version with a `sed` match on the first
  `^version = "..."` line in `pyproject.toml`, so that line must stay in
  `[tool.poetry]` form.

## Deliberate choices that look like mistakes

* Package metadata uses the legacy `[tool.poetry]` format, so `poetry check`
  emits deprecation warnings. Migrating to PEP 621 `[project]` is a deliberate
  future task - don't fix the warnings piecemeal.
* The Release workflow does not use the `.github/actions/setup-poetry`
  composite action: its build job never runs `poetry install`, so the
  action's dependency install and venv cache would be pure waste.
* CI Python version is pinned in `.github/actions/setup-poetry/action.yml`
  and `manual-release.yml` - keep in sync with `tool.poetry.dependencies`
  (see the comment there).
