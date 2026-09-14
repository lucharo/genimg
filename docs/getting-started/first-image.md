# Your first image

## Check which models you can reach

Before spending anything, ask each provider what it lists. No image is generated:

```bash
genimg models
```

```text
                 genimg models  •  cache age: 0s  •  default: (none — pass -m)
  alias           model_id                    provider  region       status
★ gdm:nb2         gemini-3.1-flash-image      google    global       listed
  gdm:nbp         gemini-3-pro-image          google    global       listed
  gdm:nb2-lite    gemini-3.1-flash-lite-image google    global       listed
  gdm:nb          gemini-2.5-flash-image      google    us-central1  listed
  oai:gi2.5       gpt-image-2.5-sunburst      openai    -            listed
  oai:gi2         gpt-image-2                 openai    -            listed
  oai:gi1.5       gpt-image-1.5               openai    -            missing
  codex:image     codex:image                 codex     -            ready
```

`listed` means the provider's list endpoint advertises the model to your credentials;
`missing` means it does not. Only a real generation proves a model serves, and on Vertex a
`missing` can be a false negative (Model Garden models are often not enumerated). Results are
cached for five days; `genimg models --refresh` re-probes, `--json` emits the table for
scripts.

## Generate

```bash
genimg "a paper-cut fox in a birch forest, warm palette" -m gdm:nb2 -o fox.png
```

```text
genimg google/direct@google gdm:nb2 → gemini-3.1-flash-image
  prompt   "a paper-cut fox in a birch forest, warm palette"
  params   n=1
  cost     $0.0670 (estimate)  id=20260914_081205_3f2a9c
  output   fox.png
  wrote fox.png (1,204,331B)
  cost $0.0670 (estimate)  •  7.9s  •  meta ~/.genimg/metadata/20260914_081205_3f2a9c.json
```

The first line names the provider, the auth mode that resolved (`direct`, from the profile
called `google`), the alias and the canonical model id. Add `--dry-run` to see the same
preview without calling the API, which is the cheapest way to check a flag combination.

Useful flags for a first session:

| Flag | What it does |
| --- | --- |
| `-m ALIAS` | model; aliases and full provider ids both work (`gdm:nb2`, `oai:gi2`, `gpt-image-2`) |
| `-o PATH` | output PNG; default is `~/.genimg/generations/<id>.png` |
| `-a 16:9` | aspect ratio, from the model's supported set |
| `-r 2K` | resolution `512 / 1K / 2K / 4K`, model dependent |
| `-q high` | OpenAI quality (`low / medium / high / auto`; GPT Image 2.5 adds `xhigh / max`) |
| `--open` | open the result (or the grid) in your browser |
| `--dry-run` | preview model, size, cost and paths; no API call |

## Save a default

```bash
genimg models set-default gdm:nb2   # or pick one in `genimg setup`
genimg "a paper-cut fox"            # -m no longer required
```

Every run is recorded. `genimg history` lists recent generations with cost and paths;
`genimg history view` is an interactive browser with in-terminal previews;
`genimg cost` totals estimated API spend.

Next: let your agent use genimg via the [bundled skill](../agents.md), or learn how to get
[genuinely different candidates](../guide/diversity.md).
