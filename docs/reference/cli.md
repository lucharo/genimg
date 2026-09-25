# CLI reference

```text
genimg "PROMPT" [REF_PATHS...] [OPTIONS]      generate (the default action)
genimg <verb> [...]                           utilities
```

`genimg` with no arguments prints help; `genimg -h` shows every generation flag; each verb
has its own `-h`. `--version` prints the installed version.

## Generate

| Flag | Short | Values | Notes |
| --- | --- | --- | --- |
| `--model` | `-m` | alias or canonical id | Required unless a default is saved. `gdm:nb2`, `oai:gi2`, `codex:image`, `gpt-image-2`, … |
| `--profile` | | profile name | A `[profiles.NAME]` table from config.toml. Default: the provider's first profile, else env detection. |
| `--output` | `-o` | path | Output PNG. Default `~/.genimg/generations/<id>.png`; `_1.._n` suffixes for `-n > 1`. |
| `--num` | `-n` | 1–10 | Number of variants; `n > 1` runs in parallel. |
| `--diverse` | `-d` | | Deliberate variety across the `n` takes. Needs `-n >= 2`. See [Diverse images](../guide/diversity.md). |
| `--deltas` | | `"a, b, c"` or `@file` | Your own per-take deltas for takes `#2..#n`; implies `-d`; parallel mode only. |
| `--mode` | | `parallel` \| `batch` | `batch` = one n-image request, Gemini only. Rejected on OpenAI. |
| `--input` | `-i` | path | Image to edit (image-to-image). |
| `REF_PATHS` | | paths after the prompt | Reference images, order preserved, not edited. |
| `--aspect-ratio` | `-a` | `1:1 16:9 9:16 4:3 3:4 3:2 2:3 4:5 5:4 21:9 …` | Model dependent; see [Models](models.md). |
| `--resolution` | `-r` | `512 1K 2K 4K` | Model dependent. OpenAI: only pairs in its size table. |
| `--quality` | `-q` | `low medium high auto`; GPT Image 2.5 adds `xhigh max` | OpenAI only. Default `medium`. |
| `--thinking` | | `minimal` \| `high` | Gemini 3.1 Flash Image only. |
| `--auth` | | `azure` \| `native` | Force an OpenAI auth mode for this run. |
| `--region` | | e.g. `global`, `us-central1` | Google only; overrides the registry region. |
| `--project` | | GCP project id | Google Vertex only. |
| `--name` | | text | Human-readable label recorded in history. |
| `--grid` | `-g` | | With `-n >= 2`, also write an HTML grid. |
| `--open` | | | Open the grid (or the image) in the browser. |
| `--dry-run` | | | Print model, resolved size, cost and planned paths; no API call. |

Model-specific constraints that the CLI enforces before calling a provider:

- OpenAI sizes come from a fixed table: `1K` supports `1:1 4:3 3:4`; `2K` adds `16:9 9:16`;
  `4K` supports `1:1 16:9 9:16`. `16:9` at `1K` and `4:3` at `4K` are rejected with the fix.
- Gemini 3.1 Flash Image accepts `512`–`4K` and every aspect from `1:8` to `8:1`; Gemini 3
  Pro Image accepts `1K`–`4K` and the classic ten aspects; the Lite model is `1K` only.
- `codex:image` accepts no `-r`, `-q`, `--thinking`, `--region`, `--project` or `--mode batch`;
  `-a` becomes a prompt request.
- Saved defaults (`default_resolution`, `default_aspect_ratio`, `default_quality`) are
  applied only when the selected model supports them; explicit flags are never discarded.

## Verbs

| Verb | Purpose | Options |
| --- | --- | --- |
| `setup` | Interactive wizard: detect credentials, fetch missing ones, live preflight, save a profile and optionally a default model. | |
| `auth` | Auth status per provider: mode, source, endpoint, credential, ready, cached model count. | `--json`, `--check` (tiny live probe per provider), `--modes` (every mode and its env vars) |
| `models` | Registry table with each model's listed/missing status from the provider's list endpoint (cached 5 days). | `--refresh`, `--aliases`, `--json` |
| `models set-default ALIAS` | Save a default model so `-m` can be omitted. | |
| `models get-default` / `clear-default` | Show or remove it. | |
| `history` | Recent generations: time, name, model, prompt, images, cost, output. | `-n/--limit`, `--summary`, `--json` |
| `history view` | Interactive browser with in-terminal previews, full prompt and paths; `yi` copies the image, `yp` its path, `?` lists keys. | |
| `cost` | Total estimated API spend (`history --summary`). | `--json` |
| `grid PATHS...` | HTML grid and carousel from existing images. | `-o`, `--open` |
| `draw [PATHS...]` | Local Draw Studio canvas server. | `--port`, `-m`, `--no-open` |
| `config` | `show` (TOML), `path`, `edit` (`$EDITOR`). | |
| `skills` | `list`, `path [skill]`, `install [agent] [skill] [--force]`, `update`, `uninstall`. Agents: `claude codex cursor opencode all`. | |

## Exit codes and output

`0` success, `1` usage or configuration error (bad flag combination, unknown model or
profile), `2` an option the parser rejects (an unknown flag, even with `--dry-run`) or a
failed generation. A `2` alone does not prove a provider request was sent. The generation
preview and result lines go to stdout and are for reading: they show paths as given and may
abbreviate the home directory as `~`. The `--json` forms (`auth`, `models`, `history`, `cost`)
print only JSON so they can be piped; the metadata sidecar and `history --json` carry
absolute paths.

## Files

| Path | Contents |
| --- | --- |
| `~/.config/genimg/config.toml` | defaults and `[profiles.*]`; see [config.toml](config.md) |
| `~/.genimg/generations/` | default output location |
| `~/.genimg/metadata/<id>.json` | one sidecar per generation: prompt, model, params, per-image deltas, cost, provenance |
| `~/.genimg/grids/` | HTML grids |
| `~/.cache/genimg/models.json` | the `genimg models` probe cache |

Override the config directory with `GENIMG_CONFIG_HOME` and the data directory with
`GENIMG_HOME`.
