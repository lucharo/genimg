# genimg

[![CI](https://img.shields.io/github/actions/workflow/status/lucharo/genimg/ci.yml?branch=main&label=CI)](https://github.com/lucharo/genimg/actions/workflows/ci.yml)
[![Python 3.11 | 3.12 | 3.13](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](pyproject.toml)
[![PyPI](https://img.shields.io/pypi/v/genimg)](https://pypi.org/project/genimg/)
[![Licence: MIT](https://img.shields.io/badge/licence-MIT-green)](LICENSE)

One simple CLI, made with both humans and agents in mind. The agent-native design is inspired
by [kenn-io](https://github.com/kenn-io) and the tools they put out, especially
[roborev](https://github.com/kenn-io/roborev) and [agentsview](https://github.com/kenn-io/agentsview).

Generate images with OpenAI and
Google DeepMind models in a unified interface, via API or via Codex with a ChatGPT
subscription. It bundles one HTML grid artefact and a drawing sketchpad for image generation,
as well as several skills for productive image generation workflows.

**Docs: [lucharo.github.io/genimg](https://lucharo.github.io/genimg/)**

```bash
uv tool install genimg
genimg setup                      # connect a provider and save a profile
genimg "a minimal fox logo, NOT a grid" -m oai:gi2.5-flare -n 4 \
  --deltas "line art, block print, brush stroke" -o fox.png -g --open
```

![The HTML grid genimg opened: four fox logos labelled base prompt, line art, block print and brush stroke](docs/assets/grid.webp)

Add the skills to Claude Code, Codex, Cursor or OpenCode with `npx skills add lucharo/genimg`.

## Docs

- [Getting started](https://lucharo.github.io/genimg/getting-started/): install, providers, first image
- [For agents](https://lucharo.github.io/genimg/agents/): the skills and what an agent can read
- [Guide](https://lucharo.github.io/genimg/guide/diversity/): diverse images, input images, Codex
- [Reference](https://lucharo.github.io/genimg/reference/cli/): CLI, models, config.toml

## Contributing

`uv sync`, then `uv run pytest` and `uv run ruff check .`. See [CONTRIBUTING.md](CONTRIBUTING.md)
and the [maintainer docs](https://lucharo.github.io/genimg/maintainers/).
