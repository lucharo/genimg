---
name: genimg
description: Generate or edit images via a single CLI that wraps Google (Gemini Nano Banana / Imagen on Vertex AI or direct API) and OpenAI (gpt-image-2 on Azure or direct). Use when the user asks to "generate an image", "create an image", "edit an image", "make a picture", "render a poster", "make a grid of images", or any image generation/editing task. Auto-detects auth from env vars. Use `-m provider:model` to switch providers (gdm:nb2, oai:gi2, gdm:nbp).
---

# genimg — multi-provider image CLI

Single command. Two providers. Same flags.

## Quick start

```bash
# Default model
genimg "a robot on a beach" -o robot.png

# Pick provider explicitly
genimg "a robot on a beach" -m oai:gi2 -o robot.png       # OpenAI gpt-image-2
genimg "a robot on a beach" -m gdm:nbp -o robot.png       # Gemini 3 Pro Image

# Edit existing image (image-to-image)
genimg "make it night" -i robot.png -o robot_night.png

# Reference images for style consistency (positional, after PROMPT)
genimg "in this style" ref1.png ref2.png -o styled.png

# Batch + auto-grid (HTML, click image to copy to clipboard)
genimg "a robot on a beach" -n 4 -g --open
```

## Auth — how it's resolved

`genimg auth` shows current state. Resolution is automatic:

**Google (Gemini / Imagen):**

| If env var set | Mode | Endpoint |
|---|---|---|
| `CLAUDE_GCP_CRED` | Vertex AI | `example-gcp-project` (override with `--project`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Vertex AI | uses `GOOGLE_CLOUD_PROJECT` |
| `GOOGLE_API_KEY` or `GEMINI_API_KEY` | Direct | `generativelanguage.googleapis.com` |

**OpenAI (gpt-image-*):**

| If env var | Mode | Endpoint |
|---|---|---|
| `OPENAI_BASE_URL` contains `azure.com` | Azure | uses `OPENAI_API_KEY` |
| `AZURE_OPENAI_ENDPOINT` set | Azure | uses `AZURE_OPENAI_API_KEY` |
| `OPENAI_API_KEY` only | Direct | `https://api.openai.com` |

To use plain OpenAI / Gemini API instead of corporate proxies: just unset the corporate env vars and export the public-API key. `genimg --auth direct` forces direct OpenAI when `OPENAI_BASE_URL` is set to Azure but you want to bypass.

## Models (`-m`)

| Alias | Canonical | Provider | Notes |
|-------|-----------|----------|-------|
| `gdm:nb2` (default) | `gemini-3.1-flash-image-preview` | Google | "Nano Banana 2", fast, cheap, 4K |
| `gdm:nbp` | `gemini-3-pro-image-preview` | Google | "Nano Banana Pro", best quality, slower |
| `gdm:nb` | `gemini-2.5-flash-image` | Google | "Nano Banana" original (GA) |
| `gdm:imagen4` / `-fast` / `-ultra` | `imagen-4.0-*-001` | Google | Imagen line (deprecating Jun 2026) |
| `oai:gi2` (or `oai:gpt-image-2`) | `gpt-image-2` | OpenAI | Best in-image text rendering |
| `oai:gi1.5` / `oai:gi1` / `oai:gi1-mini` | `gpt-image-1.5` / `gpt-image-1` / `gpt-image-1-mini` | OpenAI | Legacy/cheaper tiers |

Bare canonical IDs also accepted: `-m gpt-image-2`, `-m gemini-3.1-flash-image-preview`.

## Discovery + setting your default

```bash
genimg models                       # shows ★ on the active default
genimg models --refresh             # re-probe (status: working / 404 / 403)
genimg models set-default gdm:nbp   # save default to ~/.config/genimg/config.json
genimg models get-default           # print active default
genimg models clear-default         # revert to built-in (gdm:nb2)
```

`genimg "..."` (no `-m`) uses: user-set default → built-in `gdm:nb2`.

## Skill management

```bash
genimg skills install               # symlink ~/.claude/skills/genimg → package
genimg skills update                # re-link if package path changed
genimg skills uninstall             # remove the symlink
```

## Flags (generate)

```
PROMPT                 the text prompt (positional, quote multi-word)
REF_PATHS              reference images for style (positional, after PROMPT, space-separated)
-o, --output PATH      output PNG (default: ~/.genimg/generations/<id>.png; multi: <stem>_1.png, ...)
-m, --model NAME       alias or canonical id
-i, --input PATH       image to edit (image-to-image)
-n, --num INT          variants 1-10 (n>1 runs in parallel)
-r, --resolution       1K | 2K | 4K
-a, --aspect-ratio     1:1 | 3:4 | 4:3 | 9:16 | 16:9
-q, --quality          OpenAI only: low | medium (default) | high | auto
-g, --grid             write HTML grid to ~/.genimg/grids/<id>.html (n>=2 only)
    --open             open grid (or single image) in browser
    --region NAME      Google: override region (default from registry)
    --project ID       Google: override GCP project
    --auth MODE        OpenAI: 'azure' or 'direct' (default: auto)
```

## Auto-archive + metadata

Every generation is logged to `~/.genimg/`:

- **Image**: `-o PATH` if given, else `~/.genimg/generations/<id>.png`
- **Metadata sidecar**: always at `~/.genimg/metadata/<id>.json` — prompt, model, alias, provider, time, cost estimate, output paths, workdir, refs
- **Grid (n>=2 + `-g`)**: `~/.genimg/grids/<id>.html`

`<id>` = `YYYYMMDD_HHMMSS_<6hex>` — sortable + collision-free. Cost is shown inline (`cost ~$0.0060`) and saved in metadata.

## Notes

- If the model returns no image, it likely tripped a safety filter — rephrase the prompt
- `gemini-3.1-flash-image-preview` requires `region=global` (handled automatically by registry)
- OpenAI `--quality high` on `gpt-image-2` is 30-90s/image — heads-up printed when picked
- HTML grid embeds images as base64 — single self-contained file, sendable over Slack/email
- Multi-image (`-n N>1`) runs in parallel via `ThreadPoolExecutor` (cap 5 workers); Imagen batches server-side natively
