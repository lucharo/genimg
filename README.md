# genimg

One command for image generation across OpenAI (GPT Image), Google DeepMind (Gemini Image) and
Codex with your ChatGPT subscription. Built from the bottom up to be human and agent friendly.

**Docs: [lucharo.github.io/genimg](https://lucharo.github.io/genimg/)**

```bash
uv tool install genimg
genimg setup                                          # detect creds → validate → save a profile
genimg models                                         # what your credentials can reach, no spend
genimg "a paper-cut fox, warm palette" -m gdm:nb2 -o fox.png
```

![A genimg grid of four fox logos, each labelled with the prompt delta that produced it](docs/assets/grid.webp)

## Why genimg

- One CLI, three providers. `gdm:` Gemini Image (API key, Vertex, ADC), `oai:` GPT Image
  (api.openai.com or Azure), `codex:image` on a ChatGPT subscription. Aliases and full model
  ids both work; there is deliberately no built-in default model.
- Real variety, on purpose. `-n 4 -d` or your own `--deltas` for named directions;
  Gemini `--mode batch` lets the model differentiate a set itself.
- Edit or steer. `-i` edits an image; positional paths are references for style and layout.
- Review surfaces. `-g --open` renders a self-contained HTML grid with a carousel and copy
  buttons; `genimg draw` opens a local pen-friendly canvas.
- Agent friendly. `genimg skills install` gives Claude Code, Codex, Cursor or OpenCode the
  `genimg` skill plus infographic, refinement and image-to-app workflows. Every verb has
  `--json`; every generation leaves a metadata sidecar.

## Guide

| | |
| --- | --- |
| [Install](https://lucharo.github.io/genimg/getting-started/install/) · [Authentication](https://lucharo.github.io/genimg/getting-started/auth/) · [First image](https://lucharo.github.io/genimg/getting-started/first-image/) | getting started |
| [For agents](https://lucharo.github.io/genimg/agents/) | the bundled skill and the agent contract |
| [Diverse images](https://lucharo.github.io/genimg/guide/diversity/) · [Input and reference images](https://lucharo.github.io/genimg/guide/input-images/) · [Codex subscription](https://lucharo.github.io/genimg/guide/codex-subscription/) | the main workflows |
| [Grid and carousel](https://lucharo.github.io/genimg/surfaces/grid/) · [Draw Studio](https://lucharo.github.io/genimg/surfaces/draw-studio/) | specialised surfaces |
| [Workflow skills](https://lucharo.github.io/genimg/skills/) | infographic, refinement, image-to-app |
| [CLI](https://lucharo.github.io/genimg/reference/cli/) · [Models](https://lucharo.github.io/genimg/reference/models/) · [config.toml](https://lucharo.github.io/genimg/reference/config/) · [FAQ](https://lucharo.github.io/genimg/faq/) | reference |

The same pages live in [`docs/`](docs/) if you prefer reading source.

## Contributing

`uv sync` then `uv run pytest` and `uv run ruff check .`. See [CONTRIBUTING.md](CONTRIBUTING.md)
and the [maintainer docs](https://lucharo.github.io/genimg/maintainers/) for the release process
and how to add a provider.
