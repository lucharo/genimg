---
name: genimg
description: Generate, edit, and iterate on images with the genimg CLI (OpenAI GPT Image + Google Gemini Image + Codex subscriptions). Use whenever the user wants to create, make, render, design, edit, or vary an image, such as logos, icons, favicons, app icons, posters, diagrams, illustrations, mockups, thumbnails, concept art, stickers, hero images, or image variations/grids. Load this BEFORE running genimg; it has the non-obvious patterns (how to get real variations, edit vs reference, model/quality choice, logo & favicon recipes) that `--help` alone does not make obvious.
---

# genimg

`genimg "PROMPT" [REF_PATHS...] [OPTIONS]` runs multi-provider image generation. Outputs a PNG (`-o path`, else archived under `~/.genimg/`). `genimg` with no args prints help; `genimg auth` / `genimg setup` for credentials. The flag table below is complete for generation; do not parse `--help` to find a flag.

## User preferences

Before generating, load the `genimg-preferences` skill if it exists. Its taste overrides this skill's defaults; the current request overrides both.

The first time the user states a lasting preference about their images (a style, a palette, "always sober"), create that skill and record the preference in the user's words; add later ones to the same file. Put it where the agent loads user-level skills, next to the installed `genimg` skill: `~/.claude/skills/genimg-preferences/SKILL.md` for Claude Code, `~/.agents/skills/genimg-preferences/SKILL.md` for agents that read `~/.agents/skills/`. Use the user level even when genimg is installed in a project, so the preferences follow the user.

```markdown
---
name: genimg-preferences
description: "The user's lasting preferences for generated images. Load with genimg before every generation or edit."
---
```

The skill belongs to the user. genimg never ships it, so updating genimg never overwrites it. Create it only after the user states a preference, never from a guess.

## Flags (generation)

| Flag | Short | Values | Constraints |
| --- | --- | --- | --- |
| `--model` | `-m` | alias or canonical id (`gdm:nb2`, `oai:gi2`, `codex:image`, `gpt-image-2`) | required unless a default is saved (`genimg models get-default`) |
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
| `--name` | | one-line label | recorded in history |
| `--grid` | `-g` | flag | with `-n >= 2`, also writes an HTML grid |
| `--open` | | flag | opens the grid (or the single image) in the browser; steals focus on macOS |
| `--dry-run` | | flag | prints model, resolved size, cost and planned paths; no API call |

`codex:image` accepts none of `-q -r --thinking --auth --region --project --mode batch`; `-a` becomes a prompt request.

## The patterns that aren't obvious (read these)

- **To get N variations, use `-n N` with a SINGLE-subject prompt.** Asking the prompt to "explore variations / show options" makes the model pack a **contact sheet into one image**. Say "a SINGLE centered X, NOT a grid, not a montage" and let `-n` create the variety.
- **For simple subjects (logo, icon, single object), add `-d`/`--diverse` to `-n`.** Plain `-n` converges on near-duplicates when the prompt is simple. `-d` appends a curated style/composition delta to #2..#n (#1 keeps the base prompt); each card's delta is shown in the grid and recorded in metadata, so a pick is reproducible. `-d` alone errors: it needs `-n >= 2`. Long, complex prompts often diversify without it.
- **YOU are the tailored-diversity engine: pass your own deltas with `--deltas`.** genimg calls no text LLM. The built-in `-d` pool is generic style/lighting/framing hints tuned for illustrations and logos, and transfers poorly to diagrams, photos or technical subjects. Compose subject-specific deltas: `--deltas "blueprint schematic, hand-drawn whiteboard, isometric cutaway"` (inline form splits on commas) or `--deltas @styles.txt` (one per line, commas allowed, `#` comments). Applied in order to #2..#n. `--deltas` implies `-d`.
- **Two ways to a varied set, by intent.** (1) `--deltas` (or bare `-d`) in parallel mode works on every provider and is the most *controlled* spread: you name the axes. (2) `-d --mode batch` on Gemini sends ONE request; the model sees all n takes and curates a deliberately different *set* (verified: distinct palettes and techniques from one call). Batch may return fewer than n and is slower (~30 s vs ~8 s). **On OpenAI `--mode batch` is rejected**: GPT Image n>1 returns near-duplicates of one prompt.
- **`-i FILE` edits that image; it stays CLOSE to the input.** Use it to iterate on a chosen result ("same icon, thicker strokes"). For related but freely varied results, pass the image as a **reference after the prompt** (`genimg "new layout, same palette" ref.png -m gdm:nbp`): it guides style, not composition.
- **Iterate, don't restart:** once a candidate is close, `-i` it with a small instruction rather than regenerating from scratch.
- **Review candidates with `-g --open`** (when `-n ≥ 2`): an HTML grid with a carousel view and per-image metadata (prompt, model, params, billing, theoretical API cost). `--open` raises the browser; to load it without stealing focus on macOS, drop `--open` and run `open -g <grid.html>` on the path the CLI prints.
- **Model choice:** there is **no built-in default**. Pass `-m <alias>`, unless the user saved one (`genimg models get-default`; `genimg setup` or `models set-default` saves one). Legible in-image **text, glyphs, logos, UI** → `-m oai:gi2` (gpt-image-2). **Photographic / painterly quality** → `-m gdm:nbp` (Gemini 3 Pro). `gdm:nbp` and `gdm:nb2` are **far better than gpt-image-2 at structured diagrams**: layout, arrows, spatial instructions (see *Diagrams & infographics*). `genimg models` lists all.
- **GPT Image 2.5:** `oai:gi2.5` → `gpt-image-2.5-sunburst`, `oai:gi2.5-flare` → `gpt-image-2.5-flare`. Both generate and edit and add `-q xhigh` / `-q max`. Availability depends on the endpoint; verify with an exact-model generation. Priced from OpenAI's token calculator on 2.5's own cheaper grid (2.5 `high` costs what gi2 `medium` does). The gpt-image-2 comparisons above are not benchmarks of 2.5.
- **Codex subscription:** `genimg "PROMPT" -m codex:image -o out.png` uses the local Codex CLI and ChatGPT login (`codex login`); no API key. It starts an ephemeral Codex agent run and records the result in history. Generation, `-i`, references and `-n`/`-d` work; Codex selects the image model and size, so `-a` is a request, not a guaranteed dimension. No image-model/version selector exists: never promise GPT Image 2.5 or infer a version from the filename. A direct host `image_gen` call runs outside genimg and does not enter its history.
- **Provenance and billing:** each generation captures the C2PA claim (extracted offline, not signature-verified), generator, dimensions and hash. `billing` (`subscription` or `api`) comes from the route; `api_equivalent_cost` is a separate theoretical comparison, a rough range when native quality is unknown. Never present it as a charge or add it to subscription spend. Unknown models and prices stay unknown. Credential-bearing PNGs keep their bytes; genimg fields go in sidecars.
- **Cost:** `genimg cost` / `genimg history`. Per image at 1024x1024: `oai:gi2` medium $0.053, high $0.211; `oai:gi2.5` medium $0.013, high $0.053, max $0.211. A wide 2K render can cost less than a 1K square (gi2 medium 2048x1152 is $0.042). Estimates count output tokens only. Preflight any pricey batch with `--dry-run`.
- **Name generations you may revisit:** `--name "deep-between"` stores a label in history and metadata. Names may repeat; the timestamped ID stays unique.
- **History is automatic and read-only.** `genimg history` is a compact recent table (`-n 50` widens it); `genimg history --json` emits absolute paths. `genimg history view` is a TUI for a human to browse every image (`?` lists its keys).
- **Benchmarking:** never label one-shot CLI wall time as provider latency. Record local setup or cold-start time and provider-call time separately, and state which clock each comparison uses.
- **Agent-friendly plumbing:** `--json` on `models`, `auth`, `history` and `cost`; `models --refresh` re-probes availability (`--aliases` shows alias mappings); `auth --check` does a tiny live probe for Google/OpenAI and a login-only check for Codex; `auth --modes` lists every auth mode and the env vars it detects; `genimg config show|path|edit` inspects `~/.config/genimg/config.toml`, where `[profiles.NAME]` tables pin a provider's auth mode and non-secret settings (`--profile NAME` picks one).

## Diverse exploration across providers

For a diverse set of serious options, sample more than one model unless cost or time says otherwise:

1. Preflight providers with `genimg auth --check` and the planned calls with `--dry-run`.
2. Run a Gemini spread of four to six (for example `-n 5 -d`, or tailored `--deltas`) for broad composition and style.
3. Add 1–3 targeted `oai:gi2` variants when typography, UI or crisp editorial rendering matters. Use explicit deltas; plain repeated OpenAI samples converge.
4. Compare every candidate in one native grid: `genimg grid <all paths...> -o finalists.html --open`.
5. Put provider/model, quality, resolution, references and original index in stable filenames and a selection manifest; the standalone grid does not reconstruct cross-run provenance. If a provider or model changes after a failure, say so before presenting results.

Keep stable candidate IDs (`gemini-01`, `gpt-02`) across every shortlist and grid, and record run, model, original index, filename and liked/rejected state. Never renumber images already reviewed.

## Reviewing & sharing results with a human

- **Show before you ask.** Open the candidates and let the user look before any "which do you want?"; a pick-one question with nothing on screen gets rejected.
- **Prefer the native grid.** `genimg grid a.png b.png … -o comparison.html --open` covers candidates from several runs or providers, with the carousel and selection affordances. An arbitrary-file grid shows filenames, not per-run metadata, so the manifest stays the source of truth.
- **Many strong candidates? Point the user at Tournament.** Grids of 3 to 20 images have a Tournament button: pairwise picks, N−1 for a winner and one more for a top 3. Ask the user to paste back **Copy result (JSON)**: winner, ranking and every pick, by grid number (`#3`), filename, and model when a genimg sidecar knows it.
- **Hand back a clickable link.** Give any local HTML as a markdown `file://` link, `[grid.html](file:///abs/path/grid.html)`; users reopen it.
- **For the Claude Code preview panel, embed images as base64.** The panel sandboxes the page, so a relative `<img src="sibling.png">` renders blank there. Inline `data:image/png;base64,…`. A normal browser tab loads relative paths fine.
- **Crop a chosen PNG with Pillow** by scanning rows for the first and last dark pixels (`r/g/b < ~210`) plus a margin. `getbbox()` fails on anti-aliased near-white edges.
- **Background-key matting leaves interior holes: always solidify.** Keying out a background by colour distance turns pale subject pixels semi-transparent and leaves holes that hide at thumbnail size. Flood-fill transparency from the border to find truly external pixels, fill interior holes with the nearest opaque colour, and snap body alpha ≥ ~90 to 255. Verify at 2× zoom on the flagged region and by counting alpha pixels before and after.
- **Slice a generated sprite sheet by alpha column runs, not a fixed grid.** Columns whose alpha never passes the threshold separate irregular sprites (ignore runs under ~30 px). The same per-column coverage profile measures composition flaws before you crop.
- **Style-lock a family of assets.** Generate one hero asset, then pass it as a *reference after the prompt* (not `-i`) to every sibling. Check the reference path exists first: a missing reference fails the generation, and in a background job the error scrolls away.
- **Default to light assets** unless the user asks for dark mode or paired themes. Make a requested dark variant from the chosen finalist rather than regenerating the set.

## Product screenshots and publication copy

- For product updates, use an authentic screenshot or logo as the evidence layer and let generation add diagrams, illustration or framing around it. Pass screenshots as references for loose integration; composite deterministically when pixels must stay exact.
- User-supplied copy is authoritative. Do a full-resolution defect pass for invented dates, misspellings, leaked instructions, wrong commands and garbled labels. If publication-critical text is unreliable in the raster, add it after generation.
- Verify commands and factual labels against current project/package metadata before delivery.

## Multi-view edits without drift

- Start every view from source: use each original camera angle as `-i` and pass the same
  approved image as the locked appearance reference after the prompt.
- Change one decision per call so any drift has one attributable cause.
- Never feed a generated angle into the next angle. If a view visibly drifts, reset to the
  originals and the approved reference rather than editing the drifted result again.
- Keep failed variants as human reject examples, not model inputs.

Genimg is the controlled front end for this workflow; it is not a separate image model. Record
the provider/model actually used, such as GPT Image 2, with every result.

## Diagrams & infographics (multi-cell, arrows, layered figures)

Flowcharts, layered diagrams, anything with **arrows, a fixed grid of labelled cells, or a required spatial layout** behave differently from illustrations:

- **Model choice flips: use Gemini, not gpt-image-2.** `gdm:nbp` and `gdm:nb2` follow spatial instructions (trajectories, start markers, adjacency, "don't skip a layer") *far* better. gpt-image-2 renders crisper text but reverts to generic per-cell arrows. `gdm:nb2` is fast and cheap (~$0.05/img) and often matches `gdm:nbp` on layout, so use it for wide exploration. Reach for `oai:gi2` only when text crispness dominates and the layout is simple.
- **Fresh text-to-image beats `-i` for structure.** `-i` fixes small text and colour tweaks but ignores or mangles structural edits (reroute an arrow, move a cell) and piles up mess over rounds. When the structure is wrong, restart from a fully specified prompt. Keep `-i` for the last one or two cosmetic fixes, and pass `-a` on those edits: an unflagged gpt-image-2 `-i` can default to 1024×1024 and squash the source.
- **Pin every element.** Give an exact row→cell mapping ("Environment row: 'morning cue'; Behaviour row: 'brew' …") and state spatial rules as absolutes: "the path steps between ADJACENT rows only"; "one START dot per column"; "solid line = bottom-up, dotted = top-down".
- **Watch for prompt text leaking into the render.** A "No empty boxes." instruction once printed in the legend. Phrase constraints so they cannot read as content, and scan labels for leaked phrases.
- **Defect pass: zoom, don't eyeball.** Thumbnails hide skipped cells, duplicate icons, garbled labels and leaks. Crop each region and Read it: `magick in.png -crop WxH+X+Y +repage /tmp/col.png`.
- **Compare across runs and models with `genimg grid a.png b.png … -o cmp.html`**, paired with `open -g` for a background open. `-g` on a *generation* call writes the grid under `~/.genimg/grids/`, not the working directory; use the path the CLI prints.
- **`-q high` won't fix structural failures.** Quality sharpens rendering; a wrong arrow layout stays wrong. For `-i` edits, `-q medium` is usually enough.

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

## Defaults

- `genimg setup` if auth is missing. **Always pass `-m <alias>`** unless the user saved a default (`genimg models get-default`).
- Exploring → a Gemini spread of four to six (`-n 5 -d`) plus targeted gpt-image-2 variants, then one `genimg grid` of every output. Prefer subject-specific `--deltas`. Never run parallel shell jobs instead of `-n N`.
- Legible text/logo → `oai:gi2`. Photographic quality → `gdm:nbp`. `-q` is **OpenAI only**; the CLI rejects it on `gdm` models.
- When a human must review, generate to a real `-o` path, keep stable IDs, and open one grid with the full candidate set; don't describe images you can't show.
