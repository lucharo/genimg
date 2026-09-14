# Maintainers

How genimg is built, tested, distributed and released. Users do not need this section.

| Concern | Where |
| --- | --- |
| Source layout | `src/genimg/`: `cli.py` (Typer app), `providers/` (one plugin per backend), `auth/` (profiles and resolver), `registry.py` (aliases), `config.py`, `discovery.py` (model probes), `metadata.py` / `history.py` / `provenance.py` (sidecars), `grid.py`, `draw.py` (Studio), `setup.py` (wizard). Skills live in `skills/` and are packaged as `genimg/_skills`. |
| Tests | `uv sync --group dev` then `uv run pytest`. `tests/test_provider_contract.py` parametrises over every registered provider. |
| Lint | `uv run ruff check .` (pyflakes and import order only). |
| Build | `uv build` produces the wheel and sdist. CI runs lint and tests from the checkout; installing the built wheel in a clean environment is a manual pre-release check (see [Releasing](releasing.md)). |
| Docs | `uv sync --group docs` then `uv run zensical serve`. CI runs `zensical build --strict` on every pull request that touches the docs, and publishes to GitHub Pages on pushes to `main` once the repository is public. |
| Release | [Releasing](releasing.md): release-please and PyPI Trusted Publishing. |
| Models | [Maintaining the model list](maintaining-models.md): when to edit the registry, capability tables and prices. |
| Decisions | ADRs: [no built-in default model](adr/0001-no-built-in-default-model.md), [no org-internal defaults](adr/0002-no-org-internal-defaults.md), [providers as plugins, auth profiles](adr/0003-providers-and-auth-profiles.md). |

## Adding a provider

1. Subclass `genimg.providers.base.Provider` in `src/genimg/providers/<name>.py`: declare
   `name`, `label`, `alias_prefix`, `auth_modes`, `flags`, and implement `capabilities()`,
   `make()`, and where applicable `infer_model()`, `price()`, `probe_listed()`,
   `probe_default()`.
2. Add one `AuthProfile` subclass per auth mode in `src/genimg/auth/<name>.py` with
   `detect()`, `client()`, `validate()`, `info()`, plus `env_vars`, `secret` and
   `settings_spec` so the setup wizard and `genimg auth --modes` describe it.
3. Register it in `src/genimg/providers/__init__.py` and add curated aliases in
   `registry.py`.
4. Run the suite: the contract test checks the new provider the same way as the built-ins,
   and the CLI, cost, grid, discovery and Draw Studio pick it up from the registry.

## Roadmap

Open design work is tracked as GitHub issues:
[prompt-first `genimg ui`](https://github.com/lucharo/genimg/issues/3),
[paperbanana-style paper figures](https://github.com/lucharo/genimg/issues/4),
[skills install flow](https://github.com/lucharo/genimg/issues/5),
[image tournament in the grid](https://github.com/lucharo/genimg/issues/22),
[use-case skills above the mechanics layer](https://github.com/lucharo/genimg/issues/23).
A hosted, multi-user Draw Studio is out of scope for now (see the
[security boundary](../surfaces/draw-studio.md#security-boundary)).
