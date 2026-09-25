# Maintainers

How genimg is built, tested and shipped. You only need this section to contribute.

| Task | Command |
| --- | --- |
| Set up | `uv sync` |
| Test | `uv run pytest` |
| Lint | `uv run ruff check .` |
| Build the wheel and sdist | `uv build` |
| Build the docs | `uv run --only-group docs zensical build --strict` |

## Code layout

| Path | Holds |
| --- | --- |
| `src/genimg/cli.py` | The Typer app |
| `src/genimg/providers/` | One plugin per backend: OpenAI, Google, Codex |
| `src/genimg/auth/` | One profile class per provider and auth mode |
| `src/genimg/registry.py` | Model aliases |
| `src/genimg/draw.py`, `grid.py` | Draw Studio and the grid |
| `skills/` | Agent skills, shipped in the wheel as `genimg/_skills` |

## CI

| Workflow | Runs |
| --- | --- |
| `ci.yml` | Lint and tests on Python 3.11, 3.12 and 3.13; checks pull request titles |
| `docs.yml` | A strict docs build; deploys to GitHub Pages from `main` |
| `release.yml` | release-please and PyPI publishing |

## Releases

Pull request titles follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`,
`fix:`, `docs:`). Merges are squashed, so each title becomes a changelog line.
[release-please](https://github.com/googleapis/release-please) collects them into a Release PR
that bumps the version and writes `CHANGELOG.md`. Merging it tags the release and publishes to PyPI
through [trusted publishing](https://docs.pypi.org/trusted-publishers/), with no API tokens.

## Add a provider

1. Subclass `Provider` in `src/genimg/providers/<name>.py`.
2. Add one `AuthProfile` per auth mode in `src/genimg/auth/<name>.py`.
3. Register it in `providers/__init__.py` and add aliases in `registry.py`.
4. Run `uv run pytest`. `tests/test_provider_contract.py` checks every registered provider.

New models usually need less: see [Adding or updating a model](models.md). The
[design decisions](decisions.md) explain why the code is shaped this way. Open work is in
[GitHub issues](https://github.com/lucharo/genimg/issues).
