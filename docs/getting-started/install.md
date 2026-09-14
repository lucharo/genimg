# Install

genimg is a Python CLI. Install it as a tool with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install genimg
genimg --version
```

Upgrade later with `uv tool upgrade genimg`. Python 3.11, 3.12 and 3.13 are supported on
macOS, Linux and Windows.

!!! note "From a checkout"
    Working on genimg itself? `uv tool install --from . genimg` installs the checkout, and
    `uv run genimg …` runs it without installing. After a `uv tool` reinstall, run
    `genimg skills update` so agent skill links point at the new install.

What you get:

- the `genimg` command, with `genimg PROMPT` as the default action and a handful of utility
  verbs (`setup`, `auth`, `models`, `history`, `grid`, `draw`, `config`, `skills`);
- generations archived under `~/.genimg/` with a metadata sidecar per run, so
  `genimg history` always knows what produced an image;
- bundled skills for coding agents (see [For agents](../agents.md)).

Next: [authenticate](auth.md) with at least one provider.
