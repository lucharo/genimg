# Contributing

## Setup

`uv sync` installs the project and the dev group (pytest, ruff).

## Day to day

- Tests: `uv run pytest`
- Lint: `uv run ruff check .` (pyflakes + import order only; formatting is not enforced)
- Build: `uv build`

## Adding a provider or auth mode

Providers are plugins (see `docs/maintainers/adr/0003-providers-and-auth-profiles.md`). Subclass
`genimg.providers.base.Provider`, give it `AuthProfile` classes for its modes, register it in
`genimg/providers/__init__.py`, add curated aliases in `registry.py`, and run
`tests/test_provider_contract.py`: it parametrises over the registry, so the new provider is
checked without new test scaffolding.

## Releases

Automated with [release-please](https://github.com/googleapis/release-please) and PyPI
Trusted Publishing (OIDC, no tokens).

- Use Conventional Commit messages (`feat:`, `fix:`, `docs:`, …). CI checks PR titles because
  we squash-merge, so the title becomes the changelog entry.
- release-please keeps a **Release PR** open that bumps the version and writes `CHANGELOG.md`
  from the commits. To add a hand-written note, edit `CHANGELOG.md` on that PR before merging.
  Do it just before you merge: release-please force-pushes the branch whenever a new commit
  lands on `main`, which overwrites an early edit. (Anything you commit to `CHANGELOG.md`
  yourself is safe — release-please only ever prepends new versions above existing content.)
- Merging the Release PR tags the release and publishes to PyPI. The Friday 09:00 UTC cron
  is paused until the PyPI pending publisher exists and the first release has been merged
  by hand; see the [release checklist](docs/maintainers/releasing.md).
- The version lives only in `pyproject.toml` (`genimg.__version__` reads it from installed
  metadata).

### First release

`CHANGELOG.md` does not exist until the first release. Push a commit with `Release-As: 0.1.0`
in its body to pin the first version; release-please then opens the Release PR that creates
`CHANGELOG.md`. Write the 0.1.0 notes yourself on that PR before merging.

### PyPI (one-off)

Trusted Publishing needs a pending publisher on PyPI: project `genimg`, owner `lucharo`,
repository `genimg`, workflow `release.yml`, environment `pypi`.
