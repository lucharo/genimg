# genimg

[![Python 3.11 | 3.12 | 3.13](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](getting-started.md#install)
[![PyPI](https://img.shields.io/pypi/v/genimg)](https://pypi.org/project/genimg/)
[![Licence: MIT](https://img.shields.io/badge/licence-MIT-green)](https://github.com/lucharo/genimg/blob/main/LICENSE)

One simple CLI, made with both humans and agents in mind. The agent-native design is inspired
by [kenn-io](https://github.com/kenn-io) and the tools they put out, especially
[roborev](https://github.com/kenn-io/roborev) and [agentsview](https://github.com/kenn-io/agentsview).

Generate images with OpenAI and
Google DeepMind models in a unified interface, via API or via Codex with a ChatGPT
subscription. It bundles one HTML grid artefact and a drawing sketchpad for image generation,
as well as several skills for productive image generation workflows.

```bash
uv tool install genimg
genimg setup
```

## One prompt, four takes

```bash
genimg "a minimal fox logo, NOT a grid" -m oai:gi2.5-flare -n 4 \
  --deltas "line art, block print, brush stroke" -o fox.png -g --open
```

![The HTML grid genimg opened: four fox logos labelled base prompt, line art, block print and brush stroke](assets/grid.webp){ width="720" }

## Where next

<div class="grid cards" markdown>

- **[Getting started](getting-started.md)**: install, connect a provider, make a first image.
- **[For agents](agents.md)**: add the genimg skills to your coding agent.
- **[Diverse images](guide/diversity.md)**: get takes that really differ.
- **[Grid and carousel](visual-tools/grid.md)** and **[Draw Studio](visual-tools/draw-studio.md)**:
  review results and sketch prompts.

</div>
