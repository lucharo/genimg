# genimg

Multi-provider image generation CLI. Single command for Gemini (Vertex/direct), OpenAI (Azure/direct), and Codex with your ChatGPT subscription.

## Install

```bash
uv tool install --from . genimg
```

## Use

```bash
genimg "a robot" -m gdm:nb -o robot.png          # pick a model (no built-in default)
genimg "a robot" -m oai:gi2 -o robot.png         # OpenAI gpt-image-2
genimg "a robot" -m codex:image -o robot.png     # Codex subscription
genimg "a robot" -m oai:gi2.5 --dry-run           # GPT Image 2.5 Sunburst preview
genimg "a robot" -m oai:gi2.5-flare --dry-run     # GPT Image 2.5 Flare preview
genimg "with refs" a.png b.png -m gdm:nbp -o out.png     # reference images (positional)
genimg "edit this" -i input.png -m gdm:nb -o edited.png  # image-to-image
genimg "X" -m oai:gi2 -n 4 -g --open             # batch + auto HTML grid
genimg "X" -m oai:gi2 -n 4 -d -g --open          # diversified batch (curated per-gen prompt deltas)
genimg "X" -m oai:gi2 -n 3 --deltas "iso, blueprint"  # your own deltas (or --deltas @file, one per line)
genimg "X" -m gdm:nb2 -n 4 -d --mode batch       # ONE request, model curates a diverse set (Gemini image models only)
genimg grid *.png -o g.html --open               # standalone grid from existing files
genimg "X" -m oai:gi2 -n 6 -q high --dry-run     # preview model/params/cost, no API call
genimg "X" -m gdm:nb2 --name deep-between         # optional history label (duplicates allowed)
genimg history                                    # recent generations as a table
genimg history view                               # interactive image/history browser
genimg draw diagrams/                            # draw studio: annotate/sketch with image-editable models
genimg models                                    # discover listed models
genimg setup                                     # interactive auth wizard (also sets a default)
genimg auth                                      # show ✓/✗ readiness per provider
genimg config show                               # inspect saved config (config path|edit too)
```

There is **no built-in default model** — pass `-m <alias>`, or run `genimg setup`
(or `genimg models set-default <alias>`) to save one so you can omit `-m`.

See the [Draw Studio guide](docs/draw-studio.md) for the local canvas workflow, iPad/Apple Pencil
and remote-screen setup, security boundary, and the features that remain CLI-only. The
[FAQ](docs/faq/README.md) covers recovery, model availability and provider-specific controls.

`genimg history view` browses every recorded output image with arrow or Vim navigation, an
in-terminal preview, the full prompt and absolute provenance paths. It uses the terminal's native
image protocol when available and falls back to Unicode rendering. Press `yi` to copy the selected
image, `yp` to copy its absolute path, or `?` for all keys. `genimg history --json` remains the
non-interactive interface and always emits absolute paths, including when reading older sidecars
that recorded paths relative to `workdir`.

Inside a Codex agent, prefer its native `image_gen` tool, then
`genimg history add native.png --prompt "your prompt" -m codex:image --billing subscription`.
This archives the image without launching another agent. Genimg preserves content credentials
and records the reported generator/version, explicit subscription/API billing, and a separate
theoretical API-cost estimate or range where possible. See the
[native tool, provenance and billing guide](docs/codex-subscription.md).

## Getting the most variety

Plain `-n` samples one prompt N times and converges on near-duplicates for simple
subjects (logos, icons, single objects). Two ways to force real variety — pick by
**intent**, they're different tools, not better/worse:

- **Controlled spread — any provider.** You name the axes with `--deltas` (implies `-d`);
  takes `#2..#N` each get one of your deltas in order while `#1` stays the un-perturbed
  anchor, so supply `N-1` of them (three deltas for `-n 4`):
  ```bash
  genimg "a minimal fox logo, NOT a grid" -n 4 --deltas "line art, block print, brush stroke" -m oai:gi2 -g --open
  ```
  Best when you know *how* the takes should differ. Bare `-d` uses a generic built-in
  pool — handy for logos/icons, weaker for diagrams/photos, so prefer your own deltas there.

- **Model-curated set — Gemini only.** `-d --mode batch` on `gdm:nb2`/`gdm:nbp` sends **one**
  request and lets the model differentiate all N takes itself (distinct palettes *and*
  techniques):
  ```bash
  genimg "a minimal fox logo, NOT a grid" -n 4 -d --mode batch -m gdm:nb2 -g --open
  ```
  Slower (~30s vs ~8s parallel) but the most *coherent* varied set. Only Gemini image models
  diversify a batch: OpenAI rejects `--mode batch` outright (gpt-image n>1 returns
  near-duplicates), and on Imagen plain `--mode batch` works but can't diversify (independent
  samples), so `-d --mode batch` is rejected there too.

Either needs `-n >= 2`. `-d`/`--deltas` work everywhere; `--mode batch` variety is Gemini-only.
The two don't combine: `--deltas` is parallel-mode only — under `--mode batch` the model does
its own differentiation, so pick one path or the other.

## Skills

```bash
genimg skills list                              # show install state
genimg skills install                           # install all bundled skills to Claude
genimg skills install all                       # install all bundled skills to known agents
genimg skills install codex genimg              # targeted install
```

Bundled skills:
- `genimg`: lean CLI usage patterns.
- `genimg-infographic`: Baoyu-derived 21-layout × 22-style infographic workflow using GenIMG.
- `genimg-agent-refinement`: agent loop for inspecting outputs and removing obvious artifacts.
- `image-to-app`: staged workflow from visual directions through implementation and browser QA.

Skills install as symlinks into each agent's skills dir. If you reinstall/upgrade genimg
(e.g. via `uv tool`), re-run `genimg skills update` to refresh the links.

## Auth

Run `genimg setup` for the guided flow (detect → fetch missing → live preflight → save).

Modes:
- **Google**: `google_direct` (`GEMINI_API_KEY`/`GOOGLE_API_KEY`), `google_vertex` (service-account JSON via `GOOGLE_APPLICATION_CREDENTIALS`), or `google_vertex_adc` (`gcloud auth application-default login`).
- **OpenAI**: `openai_native` (`OPENAI_API_KEY` → api.openai.com) or `openai_azure` (`AZURE_OPENAI_API_KEY` + endpoint URL).
- **Codex**: `codex` uses the locally installed CLI and your own `codex login` with ChatGPT. No API key; normal Codex subscription limits apply. See [subscription generation](docs/codex-subscription.md).

Saved config wins over env-var auto-detection. Secrets stay in env / shell rc; non-secret values (Azure endpoint, GCP project) live in `~/.config/genimg/config.json`.

The Vertex project is resolved from `--project` → `config.gcp_project` → `GOOGLE_CLOUD_PROJECT` → the service-account JSON's `project_id` → `gcloud`'s active project (there is no hardcoded fallback).

## Models (`-m`)

Aliases: `codex:image` (runtime-selected image model), `gdm:nbp` (Pro), `gdm:nb2` (Flash), `gdm:nb`, `gdm:imagen4` (+ `-fast`/`-ultra`), `oai:gi2.5` (Sunburst), `oai:gi2.5-flare`, `oai:gi2`, `oai:gi1.5`, `oai:gi1`. Bare model IDs also accepted. Availability varies by account and deployment: `genimg models --refresh` refreshes provider-listing status for curated models, while only an exact-model generation proves that it serves.

GPT Image 2.5 uses the explicit IDs `gpt-image-2.5-sunburst` and
`gpt-image-2.5-flare` for generation and editing. Both accept `-q xhigh` and
`-q max` as well as the existing quality levels; genimg keeps its `medium` default.
The existing OpenAI size options also apply. Dated provider IDs are accepted directly.
See the [OpenAI image guide](https://developers.openai.com/api/docs/guides/image-generation).

GPT Image 2.5 per-image cost estimates are **unknown**: OpenAI publishes token rates,
but says the GPT Image 2 calculator does not estimate 2.5 token consumption.
Unknown estimates are saved as `null` and excluded from history spend totals and
priced generation counts. See [Sunburst pricing](https://developers.openai.com/api/docs/models/gpt-image-2.5-sunburst)
and [Flare pricing](https://developers.openai.com/api/docs/models/gpt-image-2.5-flare).
