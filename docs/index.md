# genimg

One command for image generation across OpenAI (GPT Image), Google DeepMind (Gemini Image)
and Codex with your ChatGPT subscription. Built from the bottom up to be human and agent
friendly: `auth`, `models`, `history` and `cost` have a `--json` form, every generation is
recorded, and a bundled skill teaches your coding agent the whole tool.

```bash
uv tool install genimg
genimg setup                              # pick a provider, validate it, save a profile
genimg "a paper-cut fox, warm palette" -m gdm:nb2 -o fox.png
```

<figure markdown>
  ![A genimg grid of four fox logos, each card labelled with the prompt delta that produced it](assets/grid.webp){ width="720" }
  <figcaption>Four takes of one prompt (<code>-n 4 --deltas "line art, block print, brush stroke"</code>, GPT Image 2.5 Flare on Azure) in the review grid genimg writes with <code>-g</code>.</figcaption>
</figure>

## Where to go

<div class="grid cards" markdown>

- **[Getting started](getting-started/install.md)**: install, authenticate, check what models
  your credentials can reach, generate a first image.
- **[For agents](agents.md)**: install the `genimg` skill so Claude Code, Codex, Cursor or
  OpenCode can generate images for you.
- **[Diverse images](guide/diversity.md)**: why `-n` alone converges, and the two ways to get
  real variety.
- **[Input and reference images](guide/input-images.md)**: edit an image or steer style from
  references.
- **[Specialised surfaces](surfaces/grid.md)**: the HTML grid and carousel, and the local Draw
  Studio canvas.
- **[Workflow skills](skills/index.md)**: infographics, refinement loops, image-to-app.

</div>

## Providers and models

| Provider | Alias prefix | Auth modes | Notes |
| --- | --- | --- | --- |
| Google DeepMind · Gemini Image | `gdm:` | Gemini API key, Vertex service account, Vertex ADC | batch mode, up to 4K |
| OpenAI · GPT Image | `oai:` | api.openai.com key, Azure OpenAI | quality levels, exact size table |
| Codex subscription | `codex:` | `codex login` with ChatGPT | no API key, Codex picks the model |

Full lists in the [models](reference/models.md) and [config.toml](reference/config.md)
references. There is deliberately no built-in default model: pass `-m`, or save one with
`genimg setup`.

## Status

genimg is pre-1.0. Releases are tagged on GitHub and published to PyPI; `main` may be ahead of
the latest release. Source, issues and roadmap: [github.com/lucharo/genimg](https://github.com/lucharo/genimg).
