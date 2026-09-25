# Providers as plugins, auth profiles in config.toml

**Status:** accepted (2026-09-14)

Every image backend is a `Provider` registered in `genimg.providers`: it declares its auth
modes, answers per-model capability questions (sizes, qualities, batch, thinking, input
limits), prices a request, infers unregistered model ids of its own shape, probes
availability, and builds its `IImageGen`. No other module branches on a provider name.

Authentication is a set of `AuthProfile` classes, one per (provider, mode). The user pins a
choice as a `[profiles.NAME]` table in `~/.config/genimg/config.toml`; with no table, the
first mode whose env vars are present is used. `--profile NAME` selects one of several.

Consequences:
- Adding a provider is one module plus registry aliases; the contract test in
  `tests/test_provider_contract.py` checks it the way it checks the built-ins.
- Capability, price and validation tables live in one place per provider and cannot drift
  between the CLI, the grid renderer and the Draw Studio.
- Secrets never enter the config file; profiles hold only non-secret settings.
- The 0.0.x `config.json` (`enabled_providers`) is migrated once, on first load.

Why: the previous design spread provider knowledge across twelve if/elif sites and three
cost tables, and modelled auth as duck-typed module functions, so a new host (Bedrock, a
second Azure resource) meant touching every consumer.
