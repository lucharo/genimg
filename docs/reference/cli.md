# CLI reference

```text
genimg "PROMPT" [REF_PATHS...] [OPTIONS]      generate (the default action)
genimg <verb> [...]                           utilities
```

`genimg --help` lists every generation flag, and each verb has its own `--help`. `--version` prints
the installed version.

## Generate

| Flag | Short | Values | Notes |
| --- | --- | --- | --- |
| `--model` | `-m` | alias or model id | Required unless a default is saved. `gdm:nb2`, `oai:gi2`, `codex:image`, `gpt-image-2`, … |
| `--profile` | | profile name | A `[profiles.NAME]` table from config.toml. Default: the provider's first profile, else env detection. |
| `--output` | `-o` | path | Output PNG. Default `~/.genimg/generations/<id>.png`; `_1.._n` suffixes for `--num > 1`. |
| `--num` | `-n` | 1–10 | Number of variants; `n > 1` runs in parallel. |
| `--diverse` | `-d` | | Deliberate variety across the `n` takes. Needs `--num >= 2`. See [Diverse images](../guide/diversity.md). |
| `--deltas` | | `"a, b, c"` or `@file` | Your own per-take deltas for takes `#2..#n`; implies `--diverse`; parallel mode only. |
| `--mode` | | `parallel` \| `batch` | `batch` = one n-image request, Gemini only. |
| `--input` | `-i` | path | Image to edit (image-to-image). |
| `REF_PATHS` | | paths after the prompt | Reference images, order preserved, not edited. |
| `--aspect-ratio` | `-a` | `1:1 16:9 9:16 4:3 3:4 …` | Model dependent; see [Models](models.md). |
| `--resolution` | `-r` | `512 1K 2K 4K` | Model dependent; see [Models](models.md). |
| `--quality` | `-q` | `low medium high auto`; GPT Image 2.5 adds `xhigh max` | OpenAI only. Default `medium`. |
| `--thinking` | | `minimal` \| `high` | Gemini 3.1 Flash Image and Flash Lite Image only. |
| `--auth` | | `azure` \| `direct` | Force an OpenAI auth mode for this run. |
| `--region` | | e.g. `global`, `us-central1` | Google only; overrides the registry region. |
| `--project` | | GCP project id | Google Vertex only. |
| `--name` | | text | Human-readable label recorded in history. |
| `--grid` | `-g` | | With `--num >= 2`, also write an HTML grid. |
| `--open` | | | Open the grid (or the image) in the browser. |
| `--dry-run` | | | Print model, size, cost and output path; no API call. |

- A flag the model cannot use fails before any API call, even on `--dry-run`.
  [Model-specific options](model-options.md) lists each model family's flags.
- A saved default the model cannot use is skipped; a flag you pass is never dropped.

## Verbs

| Verb | Purpose | Options |
| --- | --- | --- |
| `setup` | Wizard: detect credentials, ask for missing ones, test them, save a profile and optionally a default model. | |
| `auth` | Auth status per provider: mode, source, endpoint, credential, ready. | `--json`, `--check` (tiny live probe), `--modes` (every mode and its env vars) |
| `models` | Registry with each model's listed/missing status, cached for 5 days. | `--refresh`, `--aliases`, `--json` |
| `models set-default ALIAS` | Save a default so `--model` can be omitted. | |
| `models get-default` / `clear-default` | Show or remove it. | |
| `history` | Recent generations: time, name, model, prompt, images, cost, output. | `--limit/-n`, `--summary`, `--json` |
| `history view` | Interactive browser with in-terminal previews. `yi` copies the image, `yp` its path, `?` lists keys. | |
| `cost` | Total estimated spend (`history --summary`). | `--json` |
| `grid PATHS...` | HTML grid from existing images. | `--output/-o`, `--open` |
| `draw [PATHS...]` | Local Draw Studio canvas. `--host IP` serves it to other devices, and anyone who can reach that IP can generate with your credentials and open your generated and loaded images. | `--port`, `--host`, `--model/-m`, `--no-open` |
| `config` | `show`, `path`, `edit`. See [config.toml](config.md). | |
| `skills` | Prints `npx skills add lucharo/genimg`. `path [skill]` prints bundled skill sources. | |

## Exit codes and output

| Code | Meaning |
| --- | --- |
| `0` | Success |
| `1` | Usage or config error: bad flag combination, unknown model or profile |
| `2` | The parser rejected an option, or a generation failed |

- A `2` alone does not prove a request reached the provider.
- The `--json` forms print only JSON. Other output is for people and may shorten your home
  directory to `~`.

## Files

| Path | Contents |
| --- | --- |
| `~/.config/genimg/config.toml` | Defaults and `[profiles.*]` (move with `GENIMG_CONFIG_HOME`) |
| `~/.genimg/generations/` | Images (move `~/.genimg` with `GENIMG_HOME`) |
| `~/.genimg/metadata/<id>.json` | One sidecar per generation: prompt, model, params, deltas, cost, provenance |
| `~/.genimg/grids/` | HTML grids |
| `~/.cache/genimg/models.json` | The `genimg models` cache |
