# Your first image

## Check which models you can reach

Before spending anything, ask each provider what it lists. No image is generated:

```bash
genimg models
```

`listed` means the provider's list endpoint advertises the model to your credentials;
`missing` means it does not. Only a real generation proves a model serves, and on Vertex a
`missing` can be a false negative (Model Garden models are often not enumerated). Results are
cached for five days; `genimg models --refresh` re-probes, `--json` emits the table for
scripts.

## Generate

Preview the request before making an API call:

```bash
genimg "a paper-cut fox in a birch forest, warm palette" -m gdm:nb2 -o fox.png --dry-run
```

Output captured from that command on 20 September 2026 with genimg 0.1.0 and a Google
direct-API profile:

```text
genimg google/direct@google gdm:nb2 → gemini-3.1-flash-image
  prompt   "a paper-cut fox in a birch forest, warm palette"
  params   n=1
  cost     $0.0670 (estimate)  id=20260920_191605_ed70a0
  output   fox.png
dry-run: no API call made.
```

The first line names the provider, the auth mode that resolved (`direct`, from the profile
called `google`), the alias and the canonical model id. Your profile and run id will differ.
Remove `--dry-run` to generate the image:

```bash
genimg "a paper-cut fox in a birch forest, warm palette" -m gdm:nb2 -o fox.png
```

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
