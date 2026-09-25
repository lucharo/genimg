# Internal notes

Maintainer-only records. They stay in Git but are never built into the docs site or packed into the
sdist (`/internal` is in the sdist `exclude` list in `pyproject.toml`).

| File | Holds |
| --- | --- |
| [releasing.md](releasing.md) | Release runbook: setup, first release, pre-merge and post-release checks |
| [adr/](adr/) | Full decision records. The public summary is `docs/maintainers/decisions.md` |

## Open verification gaps

Moved out of the public FAQ on 25 September 2026.

- Draw Studio on iPad: the Sidecar, Tailscale and same-network routes are documented, but Apple
  Pencil input has not been checked on a real device.
- `codex:image` was verified with Codex CLI 0.153.4. Recheck after Codex upgrades, including
  whether the host exposes a model or version selector.
- Content credentials in generation records are extracted offline, not signature-verified.
- A model that `genimg models --refresh` marks as listed is advertised, not proven to serve. Only
  an exact-model generation proves it, per account, endpoint and region.
