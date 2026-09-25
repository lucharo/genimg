---
name: genimg
description: Generate and edit raster images with the genimg CLI (OpenAI GPT Image, Google Gemini Image, Codex subscription). Use before running any genimg command, and whenever the user wants an image made, edited or varied, such as a logo, icon, favicon, illustration, poster, photo, mockup, raster diagram, or a set of options to pick from. Skip it for charts and diagrams drawn as code (SVG, HTML, plotting libraries).
---

# genimg

`genimg "PROMPT" [REF_PATHS...] [OPTIONS]` writes one PNG per image (`-o path`, else under `~/.genimg/generations/`). Read generation flags from the table below rather than `--help`. The subcommands (`auth`, `setup`, `models`, `grid`, `history`, `cost`, `config`) document themselves with `--help`, and most take `--json`.

## Before the first call

1. Load the `genimg-preferences` skill if it exists. Its taste overrides this skill's defaults; the current request overrides both. When the user states a lasting preference about their images, record it as [references/preferences.md](references/preferences.md) describes.
2. Pass `-m` on every call. genimg has no built-in model; `genimg models get-default` shows one the user saved.
3. If a provider is not authenticated, `genimg auth --modes` names the env vars each auth mode reads; `genimg setup` is an interactive wizard for the user to run. `genimg auth --check` proves each provider answers with a tiny live generation; adding `--json` skips that probe.
4. Preflight any call with `-n > 1`, `-q high` or `-r 4K` with `--dry-run`: it prints model, resolved size, cost and planned paths without calling the API.

## Choosing a model

| Need | Model |
| --- | --- |
| Legible in-image text, glyphs, logos, UI | `oai:gi2` (gpt-image-2) |
| Photographic or painterly quality | `gdm:nbp` (Gemini 3 Pro Image) |
| Structured diagrams: arrows, labelled cells, fixed layout | `gdm:nb2` to explore, `gdm:nbp` for finals (see *Diagrams*) |
| No API key, the user's ChatGPT subscription | `codex:image` |

`genimg models` lists every model; `--aliases` adds the alias mappings.

- **GPT Image 2.5:** `oai:gi2.5` (`gpt-image-2.5-sunburst`) and `oai:gi2.5-flare` generate and edit, and add `-q xhigh` and `-q max`. Availability depends on the endpoint, so the first real generation is what proves the model serves. On 2.5's cheaper price grid, `high` costs what gi2 `medium` does. The model comparisons in this skill were measured on gpt-image-2, not 2.5.
- **Codex:** `codex:image` starts an ephemeral Codex agent on the user's ChatGPT login (`codex login`) and records the result in history. Generation, `-i`, references, `-n` and `-d` work. Codex picks the image model and size, so `-a` is a request and no flag selects a version: never promise GPT Image 2.5 or infer a version from a filename. A host `image_gen` tool call bypasses genimg and its history.

## Flags (generation)

| Flag | Short | Values | Constraints |
| --- | --- | --- | --- |
| `--model` | `-m` | alias or canonical id (`gdm:nb2`, `oai:gi2`, `codex:image`, `gpt-image-2`) | required unless a default is saved |
| `--output` | `-o` | PNG path | `n>1` writes `stem_1.png … stem_n.png`; default `~/.genimg/generations/<id>.png` |
| `--num` | `-n` | 1–10 | runs in parallel; pair with `-d`/`--deltas` for real variety |
| `--diverse` | `-d` | flag | needs `-n >= 2`; curated deltas for #2..#n (#1 = base prompt) |
| `--deltas` | | `"a, b, c"` or `@file` | your own deltas for #2..#n, implies `-d`; parallel mode only |
| `--mode` | | `parallel` (default) \| `batch` | `batch` = ONE n-image request, Gemini only; rejected on OpenAI |
| `--input` | `-i` | image path | image-to-image edit; stays close to the input |
| `REF_PATHS` | | paths after the prompt | references for style/layout, order preserved, never edited |
| `--aspect-ratio` | `-a` | `1:1 4:3 3:4 16:9 9:16 3:2 2:3 4:5 5:4 21:9`; `gdm:nb2`/`nb2-lite` add `1:4 1:8 4:1 8:1` | OpenAI: `16:9`/`9:16` need `-r 2K` or `4K`; `4:3`/`3:4` need `1K` or `2K` |
| `--resolution` | `-r` | `512 1K 2K 4K` | `gdm:nb2`: all four; `gdm:nbp`: `1K 2K 4K`; `gdm:nb2-lite`: `1K`; OpenAI: `1K 2K 4K` per the aspect rule; `codex:image`: none |
| `--quality` | `-q` | `low medium high auto`; `oai:gi2.5`/`gi2.5-flare` add `xhigh max` | OpenAI only; default `medium`; `high` is 30–90 s/image |
| `--thinking` | | `minimal` \| `high` | `gdm:nb2` only |
| `--profile` | | `[profiles.NAME]` from `~/.config/genimg/config.toml` | must match the model's provider; default = provider's first profile, else env detection |
| `--auth` | | `azure` \| `direct` | OpenAI only; forces a mode for one run |
| `--region` | | e.g. `global`, `us-central1` | Google only |
| `--project` | | GCP project id | Google Vertex only |
| `--name` | | one-line label | recorded in history; name any generation you may revisit |
| `--grid` | `-g` | flag | with `-n >= 2`, also writes an HTML grid under `~/.genimg/grids/` |
| `--open` | | flag | opens the grid (or the single image) in the browser; steals focus on macOS |
| `--dry-run` | | flag | prints model, resolved size, cost and planned paths; no API call |

`codex:image` accepts none of `-q -r --thinking --auth --region --project --mode batch`; `-a` becomes a prompt request.

## Getting real variations

- **Prompt for a SINGLE subject and let `-n N` make the variety.** A prompt asking to "explore variations" or "show options" packs a contact sheet into one image. Write "a SINGLE centered X, NOT a grid, not a montage". Make every set with one `-n` call, so the images share numbered outputs and one grid.
- **Add `-d` for simple subjects** (logo, icon, single object). Plain `-n` converges on near-duplicates there. `-d` appends a curated style or composition delta to #2..#n (#1 keeps the base prompt), and the grid and metadata record each delta, so a pick is reproducible. Long, complex prompts often diversify without it.
- **You are the tailored-diversity engine: write subject-specific `--deltas`.** genimg calls no text LLM, and the built-in `-d` pool is generic style, lighting and framing hints tuned for illustrations and logos; it transfers poorly to diagrams, photos and technical subjects. Pass `--deltas "blueprint schematic, hand-drawn whiteboard, isometric cutaway"` (inline splits on commas) or `--deltas @styles.txt` (one per line, commas allowed, `#` comments).
- **Pick the spread by intent.** `--deltas` or bare `-d` in parallel mode works on every provider and gives the most *controlled* spread: you name the axes. `-d --mode batch` on Gemini sends ONE request in which the model curates a deliberately different *set*; it may return fewer than n and takes about 30 s against 8 s. OpenAI rejects `--mode batch`: GPT Image n>1 returns near-duplicates of one prompt.

## Editing versus referencing

- **`-i FILE` edits that image and stays close to it.** Once a candidate is close, iterate with `-i` and a small instruction ("same icon, thicker strokes") rather than regenerating.
- **A reference after the prompt guides style, not composition.** Use it for related but freely varied results: `genimg "new layout, same palette" ref.png -m gdm:nbp`.
- **Style-lock a family of assets:** generate one hero asset, then pass it as a reference to every sibling. Check each reference path exists first; a missing reference fails the generation, and in a background job the error scrolls away.

## Showing candidates to a human

1. Generate to real `-o` paths. The output stem plus index (`gemini_3`, `gpt_1`) is each candidate's stable ID; never rename or renumber one someone has seen, and give a later round a new stem. Keep `selection-manifest.md` with run, model, delta, original index, filename and status (liked, rejected).
2. Put every candidate in one grid and open it before asking anything: `-g --open` for one run, `genimg grid a.png b.png … -o cmp.html --open` across runs or providers. A generation grid lands under `~/.genimg/grids/`; use the path the CLI prints. To open without stealing focus on macOS, drop `--open` and run `open -g <grid.html>`. An arbitrary-file grid shows filenames rather than per-run metadata, so the manifest stays the source of truth.
3. Hand the grid back as a `file://` link: `[grid.html](file:///abs/path/grid.html)`.
4. For 3 to 20 strong candidates, point the user at the grid's **Tournament** button (pairwise picks, n−1 for a winner, one more for a top 3) and ask them to paste back **Copy result (JSON)**: winner, ranking and every pick, by grid number, filename, and model when a sidecar knows it.

The step is done when the user has chosen from images on screen. For a broad spread of serious options (a brief, three to six directions, several providers, recombining the winners), load `genimg-visual-exploration` if it is installed. Without it, run a Gemini spread of four to six (`-n 5 -d` or tailored `--deltas`), add one to three `oai:gi2` variants with explicit deltas when typography or UI matters, and compare all of them in one grid. If a provider or model changes after a failure, say so before presenting results.

Make assets light unless the user asks for dark mode or paired themes; derive a requested dark variant from the chosen finalist.

## Product screenshots and publication copy

- For product updates, use an authentic screenshot or logo as the evidence layer and let generation add diagrams, illustration or framing around it. Pass screenshots as references for loose integration; composite deterministically when pixels must stay exact.
- User-supplied copy is authoritative. Do a full-resolution defect pass for invented dates, misspellings, leaked instructions, wrong commands and garbled labels. If publication-critical text is unreliable in the raster, add it after generation.
- Verify commands and factual labels against current project or package metadata before delivery.

## Multi-view edits without drift

- Start every view from source: use each original camera angle as `-i` and pass the same approved image as the locked appearance reference after the prompt.
- Change one decision per call so any drift has one attributable cause.
- Never feed a generated angle into the next angle. If a view visibly drifts, reset to the originals and the approved reference rather than editing the drifted result again.
- Keep failed variants as human reject examples, not model inputs.

genimg is the controlled front end for this workflow; it is not a separate image model. Record the provider and model actually used, such as GPT Image 2, with every result.

## Diagrams

Flowcharts, layered diagrams and anything with **arrows, a fixed grid of labelled cells, or a required spatial layout** behave differently from illustrations:

- **Model choice flips to Gemini.** `gdm:nbp` and `gdm:nb2` follow spatial instructions (trajectories, start markers, adjacency, "don't skip a layer") far better; gpt-image-2 renders crisper text but reverts to generic per-cell arrows. `gdm:nb2` costs half of `gdm:nbp` and often matches it on layout, so explore with it. Use `oai:gi2` only when text crispness dominates and the layout is simple.
- **Fix structure with a fresh prompt, cosmetics with `-i`.** `-i` handles small text and colour tweaks but ignores or mangles structural edits (reroute an arrow, move a cell) and piles up mess over rounds. When the structure is wrong, regenerate from a fully specified prompt. Keep `-i` for the last one or two cosmetic fixes and pass `-a` on them: an unflagged gpt-image-2 `-i` can default to 1024×1024 and squash the source.
- **Pin every element.** Give an exact row-to-cell mapping ("Environment row: 'morning cue'; Behaviour row: 'brew' …") and state spatial rules as absolutes: "the path steps between ADJACENT rows only"; "one START dot per column"; "solid line = bottom-up, dotted = top-down".
- **Phrase constraints so they cannot read as content.** Instructions leak into renders as labels (a "No empty boxes." instruction once printed in the legend), so scan every label for leaked phrases.
- **Zoom for the defect pass.** Thumbnails hide skipped cells, duplicate icons and garbled labels. Crop each region and read it: `magick in.png -crop WxH+X+Y +repage region.png`.
- **Quality sharpens rendering, not structure.** `-q high` leaves a wrong arrow layout wrong; `-q medium` is usually enough for `-i` edits.

## Recipes

```bash
# Explore options for a human to pick (4 takes + grid + open).
genimg "a SINGLE centered editorial illustration of a sprint board, flat vector, off-white bg, NOT a grid" -m gdm:nb2 -n 4 -g --open -a 16:9

# Cross-provider portfolio, then one native comparison grid.
genimg "a SINGLE light-mode editorial product-update poster, NOT a grid" app-light.png -m gdm:nb2 -n 5 -d -a 16:9 -o gemini.png
genimg "a SINGLE crisp light-mode editorial product-update poster, NOT a grid" app-light.png -m oai:gi2 -n 2 --deltas "screen-led split layout" -a 16:9 -r 2K -q high -o gpt.png
genimg grid gemini_*.png gpt_*.png -o finalists.html --open

# Simple subject → engineer the spread with -d (per-generation prompt deltas, shown in the grid).
genimg "a SINGLE minimal fox logo, NOT a grid" -m oai:gi2 -n 4 -d -g --open

# Let the MODEL diversify instead: one Gemini request, model differentiates its own 4 takes.
genimg "a SINGLE minimal fox logo, NOT a grid" -n 4 -d --mode batch -m gdm:nb2 -g --open

# A logo or app icon: one mark, flat, exact colours, square.
genimg "A SINGLE minimal flat-vector app icon, one mark centered, NOT a grid/montage: <subject>. Black line-art + one emerald-green accent on warm off-white. NO gradient, NO 3D, NO text." -m oai:gi2 -n 4 -g --open -a 1:1 -q high -o logo.png

# Favicon from a chosen logo (downscale; browsers render one PNG fine).
sips -z 128 128 logo_2.png --out public/favicon.png   # then <link rel="icon" href="/favicon.png">

# Edit/iterate on a chosen result (stays close to it).
genimg "same icon, slightly thicker strokes, larger marks" -m oai:gi2 -i logo_2.png -o logo-v2.png

# Match an existing style with a new layout (reference, not edit).
genimg "same palette and line weight, new composition" ref1.png ref2.png -m gdm:nbp -o styled.png

# Pick a model explicitly.
genimg "warm cinematic photo of a mountain cabin at night" -m gdm:nbp -o cabin.png
```

## Further reference

- Before reporting spend, billing, provenance or speed, read [references/cost-and-provenance.md](references/cost-and-provenance.md).
- Before cropping, matting out a background, slicing a sprite sheet, or embedding images in an HTML page of your own, read [references/post-processing.md](references/post-processing.md).
- `genimg history` lists recent generations (`--json` gives absolute paths); `genimg history view` is a TUI for the user to browse every image.
