# Developer guide

## Setup

`uv sync` installs the project and the dev group (pytest, ruff).

## Day to day

- Tests: `uv run pytest`
- Lint: `uv run ruff check .` (pyflakes + import order only; formatting is not enforced)
- Build: `uv build`

## Releases

Automated with [release-please](https://github.com/googleapis/release-please) and PyPI
Trusted Publishing (OIDC, no tokens).

- Use Conventional Commit messages (`feat:`, `fix:`, `docs:`, …). CI checks PR titles because
  we squash-merge, so the title becomes the changelog entry.
- release-please keeps a **Release PR** open that bumps the version and updates `CHANGELOG.md`.
  Edit that PR if you want to add a personal note before shipping.
- Merging the Release PR tags the release and publishes to PyPI. The Friday 09:00 UTC cron
  merges it automatically when CI is green; merge it yourself any time to ship sooner.
- The version lives only in `pyproject.toml` (`genimg.__version__` reads it from installed
  metadata).

### First release

Push a commit with `Release-As: 0.1.0` in its body to pin the first version, then merge the
Release PR that release-please opens.

### PyPI (one-off)

Trusted Publishing needs a pending publisher on PyPI: project `genimg`, owner `lucharo`,
repository `genimg`, workflow `release.yml`, environment `pypi`.
