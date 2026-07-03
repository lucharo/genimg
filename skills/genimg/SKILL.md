---
name: genimg
description: Generate, edit, and iterate on images with the genimg CLI (OpenAI gpt-image + Google Gemini/Imagen). Use whenever the user wants to create, make, render, design, edit, or vary an image — logos, icons, favicons, app icons, posters, diagrams, illustrations, mockups, thumbnails, concept art, stickers, hero images, or image variations/grids. Load this BEFORE running genimg; it has the non-obvious patterns (how to get real variations, edit vs reference, model/quality choice, logo & favicon recipes) that `--help` alone does not make obvious.
---

# genimg

`genimg "PROMPT" [REF_PATHS...] [OPTIONS]` — multi-provider image generation. Outputs a PNG (`-o path`, else archived under `~/.genimg/`). `genimg` with no args prints help; `genimg --help` lists every flag; `genimg auth` / `genimg setup` for credentials.

## The patterns that aren't obvious (read these)

- **To get N variations, use `-n N` with a SINGLE-subject prompt.** `-n` runs N generations in parallel and writes `name_1.png … name_N.png`. Do NOT ask the prompt to "explore variations / show options / a few takes" — that makes the model pack a **contact-sheet/grid into one image**. Say "a SINGLE centered X, NOT a grid, not a montage" and let `-n` create the variety.
- **For simple subjects (logo, icon, single object), add `-d`/`--diverse` to `-n`.** Plain `-n` relies on sampling temperature alone and converges on near-duplicates when the prompt is simple. `-d` appends a distinct curated style/composition delta to each generation (#1 keeps the base prompt as anchor); the delta each card used is shown in the grid and recorded in metadata, so a pick is reproducible. `-d` needs `-n >= 2` — alone it errors out. Long, complex prompts often diversify fine without it.
- **YOU are the tailored-diversity engine — pass your own deltas with `--deltas`.** genimg deliberately contains no text LLM (design invariant — image models only), and the built-in `-d` pool is generic style/lighting/framing hints tuned for illustrations/logos — it transfers poorly to diagrams, photos, or technical subjects. Compose subject-appropriate deltas yourself and pass them in one call: `--deltas "blueprint schematic, hand-drawn whiteboard, isometric cutaway"` (comma-separated, applied in order to #2..#n; #1 keeps the base prompt) or `--deltas @styles.txt` (one per line, `#` comments allowed). `--deltas` implies `-d`. Bare `-d` = quick generic spread.
- **`--mode parallel|batch` picks HOW the n generations are submitted** (orthogonal to `-d`). Default is the provider's natural mode: everything fans out as n parallel single-image requests except Imagen, which batches server-side. `--mode batch` forces ONE n-image request: OpenAI `n=4` (note: Azure deployments may serialize it — slower than parallel), Imagen `number_of_images`, Gemini a single multi-image response (model-discretionary — may return fewer than n; parallel guarantees n). **`-d --mode batch` is Gemini-only**: the model sees all n takes in one request and differentiates them itself using its own judgment — the model-knowledge alternative to the curated deltas of parallel `-d`. On OpenAI/Imagen it errors (independent samples of one prompt can't coordinate diversity).
- **`-i FILE` edits that image (image-to-image); it stays CLOSE to the input.** Use it to iterate on a chosen result ("same icon, thicker strokes"). For *related but freely varied* results, pass the image as a **reference after the prompt** (`genimg "new layout, same palette" ref.png`) instead — it guides style, not composition.
- **Review candidates with `-g --open`** (when `-n ≥ 2`): writes an HTML grid and opens it in the browser. Best way to let a human pick. The grid embeds generation metadata (collapsible prompt + a per-line panel: model, params, single cost) and offers both a grid and a carousel view.
  - **Open without stealing focus (macOS):** `--open` raises the browser to the foreground. To load it in the background instead, drop `--open` and run `open -g <grid.html>` yourself (the CLI prints the grid path). Good when the user is mid-task and doesn't want focus yanked.
- **Model choice:** the built-in default is `gdm:nb2` (Gemini 3.1 Flash) unless the user set their own (`genimg models get-default` shows the effective one) — so for legible in-image **text, glyphs, logos, UI**, pass `-m oai:gi2` (gpt-image-2) explicitly, don't rely on the default. `-m gdm:nbp` (Gemini 3 Pro) — best for **photographic / painterly quality**, and (with `gdm:nb2`) **far better than gpt-image-2 at structured diagrams** — layout, arrows, spatial instructions (see *Diagrams & infographics* below). `genimg models` lists all.
- **Quality/size (OpenAI):** `-q high` is crisp but 30–90s/image (fine with `-n`, it's parallel); `-q medium` (default) is good for exploration. `-a` aspect (`1:1 3:4 4:3 9:16 16:9`), `-r` resolution (`1K 2K 4K`).
- **Iterate, don't restart:** once a candidate is close, `-i` it with a small instruction rather than regenerating from scratch. The `genimg-agent-refinement` skill is a structured polish loop for this.
- **Cost:** `genimg cost` / `genimg history`. `-q high` + big `-n` adds up (~$0.05–0.21/image). Preflight any pricey batch with `--dry-run` — prints model, params, per-path plan, and the cost estimate without calling the API.
- **Agent-friendly plumbing:** `--json` on `models`, `auth`, `history`, and `cost` emits machine-readable output; `history -n 50` widens the window; `models --refresh` re-probes availability (`--aliases` shows alias mappings); `auth --check` does a tiny live probe per provider; `genimg config show|path|edit` inspects the saved config.

## Reviewing & sharing results with a human
- **Show before you ask.** When the user has to choose, OPEN/READ the candidates first and let them look — don't lead with a "which do you want?" prompt before anything is on screen (a premature pick-one question just gets rejected). Build a quick contact-sheet or per-section carousel HTML when there are many variants/families to wade through.
- **Hand back a clickable link.** Any local HTML you open, also give as a markdown `file://` hyperlink — `[grid.html](file:///abs/path/grid.html)` — the user routinely wants to reopen it themselves.
- **For the Claude Code preview panel, embed images as base64.** The Launch preview sandboxes the page, so `<img src="sibling.png">` (relative path) renders blank. Inline PNGs as `data:image/png;base64,…` to make it self-contained. A normally-opened browser tab loads relative paths fine — this only bites in the preview panel.
- **Crop/clean a chosen PNG with Pillow.** To trim negative space or drop a baked-in title, scan rows for the first/last with dark pixels (`r/g/b < ~210`) and crop to that ± a margin — don't trust `getbbox()`, anti-aliased near-white edges defeat it.

## Diagrams & infographics (multi-cell, arrows, layered figures)

Structured diagrams — flowcharts, layered/systems diagrams, anything with **arrows, a fixed grid of labelled cells, or a required spatial layout** — behave differently from illustrations. Hard-won rules:

- **Model choice flips: use gemini, not gpt-image-2.** `gdm:nbp` (3-pro) and `gdm:nb2` (3.1-flash) follow spatial/structural instructions (trajectories, start-markers, adjacency, "don't skip a layer") *far* better. gpt-image-2 renders crisper text but reverts to generic per-cell arrows and ignores complex layout/arrow asks. `gdm:nb2` is fast + cheap (~$0.05/img) and often matches 3-pro on layout — good for wide exploration. Reach for `oai:gi2` only when in-image text crispness dominates and the layout is simple.
- **Fresh text-to-image beats `-i` for structure.** `-i` reliably fixes small text/colour tweaks but *ignores or mangles* structural edits (reroute an arrow, dedupe icons, move a cell, change a path) and piles up mess over rounds. When the structure is wrong, **restart from a fully-specified fresh prompt**, not another `-i`. Reserve `-i` for the final one or two cosmetic fixes on the chosen image — and pass `-a` explicitly on those edits: an unflagged gpt-image-2 `-i` can default to square (1024×1024) and squish a portrait/landscape source.
- **Pin every element explicitly.** Give an exact **row→cell mapping** ("Environment row: 'morning cue'; Behaviour row: 'brew' …") and state spatial rules as absolutes: "the path steps between ADJACENT rows only, never skipping a layer"; "one START dot per column"; "solid line = bottom-up, dotted = top-down". Vague layout language drifts; explicit pinning is what fixed mis-rowed cells.
- **Watch for prompt text leaking into the render.** Meta-instructions can appear as literal labels — e.g. a "No empty boxes." instruction showed up printed in the legend. Phrase constraints so they can't be read as content, and always scan the legend/labels for leaked phrases.
- **Defect pass: zoom, don't eyeball.** Thumbnails hide skipped cells, duplicated icons, garbled/duplicated labels, and text leaks. Crop each column/region and Read it: `magick in.png -crop WxH+X+Y +repage /tmp/col.png`. Do this before declaring a candidate final.
- **Compare across runs/models with `genimg grid`.** `genimg grid a.png b.png … -o cmp.html` builds the standard gallery from arbitrary files (not just one run) — the clean way to line up gpt vs gemini vs flash takes for a human pick. Pair with `open -g` for background open. (Note: `-g` on a *generation* call writes the grid under `~/.genimg/grids/`, not the working dir — grab the path the CLI prints.)
- **`-q high` won't fix structural failures.** Quality only sharpens rendering; a wrong arrow layout stays wrong at any quality. For `-i` edits, `-q medium` is usually enough (high can fumble more).

## Recipes

```bash
# Explore options for a human to pick (4 takes + grid + open).
genimg "a SINGLE centered editorial illustration of a sprint board, flat vector, off-white bg, NOT a grid" -n 4 -g --open -a 16:9

# Simple subject → engineer the spread with -d (per-generation prompt deltas, shown in the grid).
genimg "a SINGLE minimal fox logo, NOT a grid" -n 4 -d -g --open

# Let the MODEL diversify instead: one Gemini request, model differentiates its own 4 takes.
genimg "a SINGLE minimal fox logo, NOT a grid" -n 4 -d --mode batch -m gdm:nb2 -g --open

# A logo / app icon — one mark, flat, exact colors, square.
genimg "A SINGLE minimal flat-vector app icon, one mark centered, NOT a grid/montage: <subject>. Black line-art + one emerald-green accent on warm off-white. NO gradient, NO 3D, NO text." -n 4 -g --open -a 1:1 -q high -o logo.png

# Favicon from a chosen logo (downscale; browsers render one PNG fine).
sips -z 128 128 logo_2.png --out public/favicon.png   # then <link rel="icon" href="/favicon.png">

# Edit/iterate on a chosen result (stays close to it).
genimg "same icon, slightly thicker strokes, larger marks" -i logo_2.png -o logo-v2.png

# Match an existing style with a new layout (reference, not edit).
genimg "same palette and line weight, new composition" ref1.png ref2.png -o styled.png

# Pick a model explicitly.
genimg "warm cinematic photo of a mountain cabin at night" -m gdm:nbp -o cabin.png
```

## Defaults
- `genimg setup` if auth is missing; omit `-m` unless the user wants a specific provider.
- Exploring → `-n 4 -g --open`; never run parallel shell jobs as a substitute for `-n N`. For simple subjects add `-d` so the tool varies style/composition per generation; for complex prompts you can also **vary styles across prompts yourself** (photorealistic, illustrated, cartoony, sketch, minimalist) to find the right register in round 1, not round 2.
- Legible text/logo → `oai:gi2`. Photographic quality → `gdm:nbp`. `-q`/`--quality` is **oai:gi2 only** — the CLI rejects it on gdm models, so omit it there.
- When a human must review, generate to a real `-o` path and `--open` the grid; don't describe images you can't show — open or read them.
