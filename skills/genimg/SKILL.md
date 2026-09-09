---
name: genimg
description: Generate, edit, and iterate on images with the genimg CLI (OpenAI gpt-image + Google Gemini/Imagen + Codex subscriptions). Use whenever the user wants to create, make, render, design, edit, or vary an image — logos, icons, favicons, app icons, posters, diagrams, illustrations, mockups, thumbnails, concept art, stickers, hero images, or image variations/grids. Load this BEFORE running genimg; it has the non-obvious patterns (how to get real variations, edit vs reference, model/quality choice, logo & favicon recipes) that `--help` alone does not make obvious.
---

# genimg

`genimg "PROMPT" [REF_PATHS...] [OPTIONS]` — multi-provider image generation. Outputs a PNG (`-o path`, else archived under `~/.genimg/`). `genimg` with no args prints help; `genimg --help` lists every flag; `genimg auth` / `genimg setup` for credentials.

## The patterns that aren't obvious (read these)

- **To get N variations, use `-n N` with a SINGLE-subject prompt.** `-n` runs N generations in parallel and writes `name_1.png … name_N.png`. Do NOT ask the prompt to "explore variations / show options / a few takes" — that makes the model pack a **contact-sheet/grid into one image**. Say "a SINGLE centered X, NOT a grid, not a montage" and let `-n` create the variety.
- **For simple subjects (logo, icon, single object), add `-d`/`--diverse` to `-n`.** Plain `-n` relies on sampling temperature alone and converges on near-duplicates when the prompt is simple. `-d` appends a distinct curated style/composition delta to each generation (#1 keeps the base prompt as anchor); the delta each card used is shown in the grid and recorded in metadata, so a pick is reproducible. `-d` needs `-n >= 2` — alone it errors out. Long, complex prompts often diversify fine without it.
- **YOU are the tailored-diversity engine — pass your own deltas with `--deltas`.** genimg does not call a text LLM to compose variations; the built-in `-d` pool is generic style/lighting/framing hints tuned for illustrations/logos — it transfers poorly to diagrams, photos, or technical subjects. Compose subject-appropriate deltas yourself and pass them in one call: `--deltas "blueprint schematic, hand-drawn whiteboard, isometric cutaway"` (comma-separated, applied in order to #2..#n; #1 keeps the base prompt) or `--deltas @styles.txt` (one per line, `#` comments allowed). `--deltas` implies `-d`. Bare `-d` = quick generic spread.
- **`--mode batch` is Google-only** (orthogonal to `-d`): ONE n-image request — a Gemini multi-image response (model-discretionary, may return fewer than n; parallel guarantees n) or Imagen `number_of_images`. **On OpenAI it's rejected outright**: gpt-image n>1 returns near-duplicate independent samples of one prompt (verified live) — pure wasted spend. Default mode stays the provider's natural one (parallel everywhere except Imagen).
- **The two combos to reach for** — pick by intent, they're different tools not better/worse: (1) **`--deltas` (or bare `-d`) in parallel mode — works on ALL providers** = the most *controlled* spread (you name the axes); (2) **`-d --mode batch` on Gemini** — the model sees all n takes in one request and curates a deliberately different *set* (verified: distinct palettes AND techniques, e.g. line-art / block-print / brush-stroke / tangram from one call) = the most *coherent* varied set. Batch is Gemini-only and slower (~30s vs ~8s parallel).
- **`-i FILE` edits that image (image-to-image); it stays CLOSE to the input.** Use it to iterate on a chosen result ("same icon, thicker strokes"). For *related but freely varied* results, pass the image as a **reference after the prompt** (`genimg "new layout, same palette" ref.png`) instead — it guides style, not composition.
- **Review candidates with `-g --open`** (when `-n ≥ 2`): writes an HTML grid and opens it in the browser. Best way to let a human pick. The grid embeds generation metadata (collapsible prompt + a per-line panel: model, params, billing and theoretical API cost) and offers both a grid and a carousel view.
  - **Open without stealing focus (macOS):** `--open` raises the browser to the foreground. To load it in the background instead, drop `--open` and run `open -g <grid.html>` yourself (the CLI prints the grid path). Good when the user is mid-task and doesn't want focus yanked.
- **Model choice:** there is **no built-in default** — pass `-m <alias>` explicitly, or the user may have saved one (`genimg models get-default` shows it; `genimg setup` / `models set-default` to save). For legible in-image **text, glyphs, logos, UI**, use `-m oai:gi2` (gpt-image-2). `-m gdm:nbp` (Gemini 3 Pro) — best for **photographic / painterly quality**, and (with `gdm:nb2`) **far better than gpt-image-2 at structured diagrams** — layout, arrows, spatial instructions (see *Diagrams & infographics* below). `genimg models` lists all.
- **GPT Image 2.5:** `oai:gi2.5` resolves to `gpt-image-2.5-sunburst`; `oai:gi2.5-flare` resolves to `gpt-image-2.5-flare`. Both support generation, editing and `-q xhigh` / `-q max`. Availability depends on the endpoint; verify an exact-model generation. Their per-image costs are unknown, stored as `null`, and excluded from spend totals. The GPT Image 2 comparisons above are not benchmarks of 2.5.
- **Codex subscription, native first:** when the host exposes `image_gen`, call it directly, then archive its returned file with `genimg history add native.png --prompt "PROMPT" -m codex:image --billing subscription` (optional `-o out.png`, `-i original.png`, repeated `--ref reference.png`). This creates provenance/history without a second agent. Follow the host tool's image-reference and display instructions. It has no image-model/version selector; never promise GPT Image 2.5 or infer a version from the filename.
- **Codex CLI fallback:** when no native image tool is available, `genimg "PROMPT" -m codex:image -o out.png` uses the user's local Codex CLI and ChatGPT login (`codex login`). No API key. Generation, `-i`, references and `-n`/`-d` work; Codex selects the image model and size. `-a` is a prompt request, not a guaranteed dimension. Omit `-q`, `-r`, `--thinking`, `--auth`, `--region`, `--project` and `--mode batch`. This starts an ephemeral Codex agent run.
- **Provenance and billing:** preserve native originals and use `history add` to capture the active C2PA claim, generator/version, actions, signing information, dimensions and hash. Claims are extracted offline, not signature-verified. Billing (`subscription` or `api`) is separate from `api_equivalent_cost`; native quality is unknown, so known reported models receive a rough low-to-high output-cost range. Missing/ambiguous model provenance and unknown prices stay unknown. Never present this theoretical comparison as a charge or add it to subscription spend. Credential-bearing PNGs keep their bytes unchanged; genimg fields live in sidecars.
- **Quality/size (OpenAI):** `-q medium` remains genimg's default; `low`, `high` and `auto` are also available, with `xhigh` and `max` on GPT Image 2.5 only. `-a` aspect (`1:1 3:4 4:3 9:16 16:9`), `-r` resolution (`1K 2K 4K`).
- **Iterate, don't restart:** once a candidate is close, `-i` it with a small instruction rather than regenerating from scratch. The `genimg-agent-refinement` skill is a structured polish loop for this.
- **Cost:** `genimg cost` / `genimg history`. `-q high` + big `-n` adds up (~$0.05–0.21/image). Preflight any pricey batch with `--dry-run` — prints model, params, per-path plan, and the cost estimate without calling the API.
- **Name generations you may revisit.** Pass `--name "deep-between"` to store an optional human label in history and unsigned PNG metadata. Credential-bearing PNGs keep genimg fields in sidecars. Names may repeat; the timestamped generation ID remains unique.
- **Browse history interactively.** `genimg history` stays a compact recent table; `genimg history view` opens every recorded output in a scrollable TUI with full prompt/path/model details and the terminal's highest-quality supported image protocol, falling back to Unicode. Use arrows or `j`/`k`, Enter/`o` to open, `yi` to copy the image, `yp` to copy its absolute path, and `?` for all keys. `genimg history --json` emits absolute paths.
- **Benchmarking:** never label one-shot CLI wall time as provider generation latency. Record local
  setup or cold-start time and provider-call time separately, and state which clock each comparison
  uses.
- **Agent-friendly plumbing:** `--json` on `models`, `auth`, `history`, and `cost` emits machine-readable output; `history -n 50` widens the window; `models --refresh` re-probes availability (`--aliases` shows alias mappings); `auth --check` does a tiny live probe for Google/OpenAI and a login-only check for Codex; `genimg config show|path|edit` inspects the saved config.

## Diverse exploration across providers

When the user asks for a diverse set of serious options, diversity means more than
sampling one model. Unless cost/time constraints say otherwise:

1. Preflight providers with `genimg auth --check` and the planned calls with `--dry-run`.
2. Run a Gemini/Nano Banana batch with a chosen count from four through six (for example
   `-n 5 -d`) or tailored `--deltas` for broad composition and style exploration.
3. Run 1–3 targeted `oai:gi2` variants—especially when typography, UI, or crisp editorial
   rendering matters. Use explicit deltas; plain repeated OpenAI samples converge.
4. Compare every candidate together with the native arbitrary-file grid:
   `genimg grid <all paths...> -o finalists.html --open`.
5. Label the actual provider/model, quality, resolution, references, and original index
   in stable filenames and a selection manifest. The standalone grid does not reconstruct
   cross-run provenance from the input PNGs.
   If a provider/model changes after a failure, disclose it before presenting results.

Keep stable candidate IDs across every shortlist and grid (for example `gemini-01`,
`gpt-02`). A small selection manifest should preserve run, model, original index,
filename, and liked/rejected state; never renumber previously reviewed images.

## Reviewing & sharing results with a human
- **Show before you ask.** When the user has to choose, OPEN/READ the candidates first and let them look — don't lead with a "which do you want?" prompt before anything is on screen (a premature pick-one question just gets rejected). Build a quick contact-sheet or per-section carousel HTML when there are many variants/families to wade through.
- **Prefer the native grid.** Use `genimg grid a.png b.png … -o comparison.html --open` for
  candidates from multiple runs or providers. Do not build throwaway HTML when the native
  grid can represent the set. It preserves the carousel and selection affordances, but an
  arbitrary-file grid currently shows filenames rather than full per-run metadata—keep the
  manifest as the source of truth.
- **Hand back a clickable link.** Any local HTML you open, also give as a markdown `file://` hyperlink — `[grid.html](file:///abs/path/grid.html)` — the user routinely wants to reopen it themselves.
- **For the Claude Code preview panel, embed images as base64.** The Launch preview sandboxes the page, so `<img src="sibling.png">` (relative path) renders blank. Inline PNGs as `data:image/png;base64,…` to make it self-contained. A normally-opened browser tab loads relative paths fine — this only bites in the preview panel.
- **Crop/clean a chosen PNG with Pillow.** To trim negative space or drop a baked-in title, scan rows for the first/last with dark pixels (`r/g/b < ~210`) and crop to that ± a margin — don't trust `getbbox()`, anti-aliased near-white edges defeat it.
- **Background-key matting leaves interior holes — always solidify.** Keying out a background by colour-distance erodes PALE subject pixels (cream chimneys, light facades) into semi-transparency and leaves border-unreachable transparent holes that read as "see-through" at full size but hide at thumbnail (a real one: 77k bad pixels shipped twice before the root cause was measured). Fix: flood-fill transparency from the border to find truly-external pixels, interior-fill the rest with the nearest opaque colour, snap body alpha ≥~90 to 255. Verify at 2× zoom on the exact region that was flagged AND by counting alpha pixels before/after — never by eyeballing a thumbnail.
- **Slice a generated sprite sheet by alpha column-runs, not a fixed grid.** After matting, columns whose alpha never exceeds threshold separate irregular-width sprites cleanly (ignore runs <~30px). The same per-column coverage profile diagnoses composition flaws before you crop anything — "plants collapse to 0% coverage at 70% width" is measurable, not a squint.
- **Style-lock a family of assets.** Generate one hero asset first, then pass it as a *reference image* (after the prompt, not `-i`) to every sibling generation — style stays consistent across a growing set far better than re-describing the style in words each time. Verify the ref path exists before a batch: a missing reference fails the generation, and in a background job the error scrolls away silently.
- **Default to light assets.** Use light-mode screenshots and light visual themes unless the
  user explicitly requests dark mode or paired themes. After a finalist is chosen, make a
  requested dark variant from that finalist rather than regenerating the whole portfolio.

## Product screenshots and publication copy

- For product updates, prefer an authentic screenshot/logo as the evidence layer and let
  generation add diagrams, illustration, or editorial framing around it. Pass screenshots
  as references for loose integration; use deterministic compositing when pixels must remain exact.
- Treat user-supplied copy as authoritative. Do a full-resolution defect pass for invented
  dates, misspellings, leaked instructions, wrong commands, and garbled labels. If publication-
  critical text is not reliable in the raster, add it deterministically after generation.
- Verify commands and factual labels against current project/package metadata before delivery.

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
genimg "a SINGLE centered editorial illustration of a sprint board, flat vector, off-white bg, NOT a grid" -m gdm:nb2 -n 4 -g --open -a 16:9

# Cross-provider portfolio, then one native comparison grid.
genimg "a SINGLE light-mode editorial product-update poster, NOT a grid" app-light.png -m gdm:nb2 -n 5 -d -a 16:9 -o gemini.png
genimg "a SINGLE crisp light-mode editorial product-update poster, NOT a grid" app-light.png -m oai:gi2 -n 2 --deltas "screen-led split layout" -a 16:9 -q high -o gpt.png
genimg grid gemini_*.png gpt_*.png -o finalists.html --open

# Simple subject → engineer the spread with -d (per-generation prompt deltas, shown in the grid).
genimg "a SINGLE minimal fox logo, NOT a grid" -m oai:gi2 -n 4 -d -g --open

# Let the MODEL diversify instead: one Gemini request, model differentiates its own 4 takes.
genimg "a SINGLE minimal fox logo, NOT a grid" -n 4 -d --mode batch -m gdm:nb2 -g --open

# A logo / app icon — one mark, flat, exact colors, square.
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
- `genimg setup` if auth is missing. **Always pass `-m <alias>`** — there is no built-in default; omit it only when the user has saved one (`genimg models get-default`).
- Exploring → choose a Gemini spread of four through six images (for example **`-n 5 -d`**)
  plus targeted GPT Image 2 variants, then
  one native `genimg grid` containing all outputs. Use subject-specific `--deltas` where
  possible; on Gemini, `-d --mode batch` gives a coherent model-curated set. Plain `-n`
  without `-d` converges on near-duplicates. Never run parallel shell jobs instead of `-n N`.
- Legible text/logo → `oai:gi2`. Photographic quality → `gdm:nbp`. `-q`/`--quality` is **OpenAI only** — the CLI rejects it on gdm models, so omit it there.
- When a human must review, generate to a real `-o` path, retain stable IDs, and open one
  native grid containing the full candidate set; don't describe images you can't show.
