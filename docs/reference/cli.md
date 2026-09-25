# CLI reference

- One section per command. `genimg COMMAND --help` prints the same flags; `genimg --version` prints
  the version.

## genimg PROMPT

- Generates images. With a saved default model, the prompt is all you must pass.

```text
genimg "PROMPT" [REF_PATHS...] [OPTIONS]
```

| Flag | Short | Values | Notes |
| --- | --- | --- | --- |
| `--model` | `-m` | alias or model id | Required unless a default is saved. `gdm:nb2`, `oai:gi2`, `codex:image`, `gpt-image-2`, … |
| `--profile` | | profile name | A `[profiles.NAME]` table in config.toml. Default: the provider's profile, else env detection. |
| `--name` | | text | Label recorded in history. |
| `--input` | `-i` | path | Image to edit. |
| `REF_PATHS` | | paths after the prompt | Reference images, kept in order, never edited. |
| `--num` | `-n` | 1 to 10 | Number of variants. Separate parallel requests unless `--mode batch`. |
| `--diverse` | `-d` | | Deliberate variety across the takes. Needs `--num` of 2 or more. See [Diverse images](../guide/diversity.md). |
| `--deltas` | | `"a, b, c"` or `@file` | Your own deltas for takes 2 to n. Implies `--diverse`. Parallel mode only. |
| `--mode` | | `parallel` \| `batch` | `batch` sends one n-image request. Gemini only. |
| `--aspect-ratio` | `-a` | `1:1 16:9 9:16 4:3 3:4 …` | Depends on the model; see [Models](models.md). |
| `--resolution` | `-r` | `512 1K 2K 4K` | Depends on the model; see [Models](models.md). |
| `--output` | `-o` | path | Default `~/.genimg/generations/<id>.png`, with `_1` to `_n` for several takes. |
| `--grid` | `-g` | | With 2 or more takes, also writes an HTML grid. |
| `--open` | | | Opens the grid, or the image, in the browser. |
| `--dry-run` | | | Prints model, size, cost and output path. No API call. |
| `--quality` | `-q` | `low medium high auto`; GPT Image 2.5 adds `xhigh max` | OpenAI only. Default `medium`. |
| `--auth` | | `azure` \| `direct` | OpenAI only. Forces an auth mode for this run. |
| `--thinking` | | `minimal` \| `high` | Gemini 3.1 Flash Image and Flash Lite Image only. |
| `--region` | | `global`, `us-central1`, … | Google only. Overrides the registry region. |
| `--project` | | GCP project id | Google Vertex only. |

- A flag the model cannot use fails before any API call, even with `--dry-run`.
  [Model-specific options](model-options.md) lists each family's flags.
- A saved default the model cannot use is skipped. A flag you pass is never dropped.

## genimg setup

- Takes you from nothing to a working profile: finds or asks for credentials, tests them, saves a
  profile and, if you pick one, a default model. Walkthrough in [Getting started](../getting-started.md).

```text
genimg setup
```

## genimg auth

- Shows each provider's active auth mode and whether it is ready.

```text
genimg auth \
  [--check] \
  [--json] \
  [--modes]
```

| Flag | Effect |
| --- | --- |
| `--check` | Runs a tiny live generation per provider. Codex checks the login only. |
| `--json` | JSON output. |
| `--modes` | Lists every auth mode and the env vars it detects. |

## genimg models

- Lists every model, its alias, and whether the provider's model list includes it. Cached for 5 days.

```text
genimg models \
  [--refresh] \
  [--aliases] \
  [--json]
genimg models set-default ALIAS
genimg models get-default
genimg models clear-default
```

| Flag or subcommand | Effect |
| --- | --- |
| `--refresh` | Probes again instead of reading the cache. |
| `--aliases` | Includes alias-only entries. |
| `--json` | JSON output. |
| `set-default ALIAS` | Saves a default, so you can drop `--model`. Takes an alias or a model id. |
| `get-default` | Prints the saved default. |
| `clear-default` | Removes it; `--model` is required again. |

## genimg history

- Lists recent generations with name, model, prompt, cost and output path.

```text
genimg history \
  [--limit N] \
  [--summary] \
  [--json]
genimg history view
```

| Flag or subcommand | Effect |
| --- | --- |
| `--limit`, `-n` | Rows, 1 to 200. Default 20. |
| `--summary` | Total estimated spend instead of rows. |
| `--json` | JSON output. |
| `view` | Browses every generation in the terminal with image previews. `yi` copies the image, `yp` its path, `?` lists keys. |

## genimg cost

- Prints your total estimated spend. Same as `genimg history --summary`.

```text
genimg cost [--json]
```

## genimg grid

- Turns existing images into an HTML grid. See [Grid and carousel](../visual-tools/grid.md).

```text
genimg grid PATHS... \
  [--output PATH] \
  [--open]
```

| Flag | Effect |
| --- | --- |
| `--output`, `-o` | Default `~/.genimg/grids/<timestamp>.html`. |
| `--open` | Opens the grid in the browser. |

## genimg draw

- Opens Draw Studio, a local canvas to sketch or annotate, then generate.
  See [Draw Studio](../visual-tools/draw-studio.md).

```text
genimg draw [PATHS...] \
  [--port PORT] \
  [--host IP] \
  [--model ALIAS] \
  [--no-open]
```

| Flag | Effect |
| --- | --- |
| `PATHS` | Images or folders to load. |
| `--port` | Default `8788`; moves up if busy. |
| `--host` | Default `127.0.0.1`. Use your LAN or Tailscale IP to draw from a tablet. |
| `--model`, `-m` | Starting model. Default: your saved default, else `gdm:nb2`. |
| `--no-open` | Does not open the browser. |

!!! warning "`--host` shares your credentials"
    Anyone who can reach that IP can generate with your credentials and open your generated and
    loaded images.

## genimg config

- Reads or edits your saved [config.toml](config.md).

```text
genimg config show
genimg config path
genimg config edit
```

| Subcommand | Effect |
| --- | --- |
| `show` | Prints the config as TOML. |
| `path` | Prints the file path. |
| `edit` | Opens the file in `$EDITOR`. |

## genimg skills

- Prints the install command for the bundled [agent skills](../skills/index.md):
  `npx skills add lucharo/genimg`, which needs Node.js.

```text
genimg skills
genimg skills path [SKILL]
```

| Subcommand | Effect |
| --- | --- |
| `path [SKILL]` | Prints a skill's source folder. Default `genimg`; `all` lists every skill. |

## Exit codes and output

| Code | Meaning |
| --- | --- |
| `0` | Success |
| `1` | Usage or config error: bad flag combination, unknown model or profile |
| `2` | The parser rejected an option, or a generation failed |

- A `2` alone does not prove a request reached the provider.
- `--json` forms print only JSON. Other output is for people and may shorten your home directory to
  `~`.

## Files

| Path | Contents |
| --- | --- |
| `~/.config/genimg/config.toml` | Defaults and `[profiles.*]`. Move with `GENIMG_CONFIG_HOME`. |
| `~/.genimg/generations/` | Images. Move `~/.genimg` with `GENIMG_HOME`. |
| `~/.genimg/metadata/<id>.json` | One file per generation: prompt, model, params, deltas, cost, provenance. |
| `~/.genimg/grids/` | HTML grids |
| `~/.cache/genimg/models.json` | The `genimg models` cache |
