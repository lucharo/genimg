# genimg

Multi-provider image generation CLI. Single command for Gemini (Vertex/direct) and OpenAI (Azure/direct).

## Install

```bash
uv tool install --from . genimg
```

## Use

```bash
genimg "a robot" -m gdm:nb -o robot.png          # pick a model (no built-in default)
genimg "a robot" -m oai:gi2 -o robot.png         # OpenAI gpt-image-2
genimg "with refs" a.png b.png -m gdm:nbp -o out.png     # reference images (positional)
genimg "edit this" -i input.png -m gdm:nb -o edited.png  # image-to-image
genimg "X" -m oai:gi2 -n 4 -g --open             # batch + auto HTML grid
genimg "X" -m oai:gi2 -n 4 -d -g --open          # diversified batch (curated per-gen prompt deltas)
genimg "X" -m oai:gi2 -n 3 --deltas "iso, blueprint"  # your own deltas (or --deltas @file, one per line)
genimg "X" -m gdm:nb2 -n 4 -d --mode batch       # ONE request, model curates a diverse set (Google-only; rejected on OpenAI)
genimg grid *.png -o g.html --open               # standalone grid from existing files
genimg "X" -m oai:gi2 -n 6 -q high --dry-run     # preview model/params/cost, no API call
genimg draw diagrams/                            # draw studio: annotate/sketch on a canvas → generate
genimg models                                    # discover listed models
genimg setup                                     # interactive auth wizard (also sets a default)
genimg auth                                      # show ✓/✗ readiness per provider
genimg config show                               # inspect saved config (config path|edit too)
```

There is **no built-in default model** — pass `-m <alias>`, or run `genimg setup`
(or `genimg models set-default <alias>`) to save one so you can omit `-m`.

## Skills

```bash
genimg skills list                              # show install state
genimg skills install                           # install all bundled skills to Claude
genimg skills install all                       # install all bundled skills to known agents
genimg skills install codex genimg              # targeted install
```

Bundled skills:
- `genimg`: lean CLI usage patterns.
- `genimg-agent-refinement`: agent loop for inspecting outputs and removing obvious artifacts.

Skills install as symlinks into each agent's skills dir. If you reinstall/upgrade genimg
(e.g. via `uv tool`), re-run `genimg skills update` to refresh the links.

## Auth

Run `genimg setup` for the guided flow (detect → fetch missing → live preflight → save).

Modes:
- **Google**: `google_direct` (`GEMINI_API_KEY`/`GOOGLE_API_KEY`), `google_vertex` (service-account JSON via `GOOGLE_APPLICATION_CREDENTIALS`), or `google_vertex_adc` (`gcloud auth application-default login`).
- **OpenAI**: `openai_native` (`OPENAI_API_KEY` → api.openai.com) or `openai_azure` (`AZURE_OPENAI_API_KEY` + endpoint URL).

Saved config wins over env-var auto-detection. Secrets stay in env / shell rc; non-secret values (Azure endpoint, GCP project) live in `~/.config/genimg/config.json`.

The Vertex project is resolved from `--project` → `config.gcp_project` → `GOOGLE_CLOUD_PROJECT` → the service-account JSON's `project_id` → `gcloud`'s active project (there is no hardcoded fallback).

## Models (`-m`)

Aliases: `gdm:nbp` (Pro), `gdm:nb2` (Flash), `gdm:nb`, `gdm:imagen4` (+ `-fast`/`-ultra`), `oai:gi2`, `oai:gi1.5`, `oai:gi1`. Bare model IDs also accepted. Availability varies by account/deployment — run `genimg models` to see what your credentials can reach.
