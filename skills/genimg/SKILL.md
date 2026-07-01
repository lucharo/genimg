---
name: genimg
description: Generate, edit, and iterate on images with the genimg CLI (OpenAI gpt-image + Google Gemini/Imagen). Use whenever the user wants to create, make, render, design, edit, or vary an image — logos, icons, favicons, app icons, posters, diagrams, illustrations, mockups, thumbnails, concept art, stickers, hero images, or image variations/grids. Load this BEFORE running genimg; it has the non-obvious patterns (how to get real variations, edit vs reference, model/quality choice, logo & favicon recipes) that `--help` alone does not make obvious.
---

# genimg

`genimg "PROMPT" [REF_PATHS...] [OPTIONS]` — multi-provider image generation. Outputs a PNG (`-o path`, else archived under `~/.genimg/`). `genimg` with no args prints help; `genimg --help` lists every flag; `genimg auth` / `genimg setup` for credentials.

## The patterns that aren't obvious (read these)

- **To get N variations, use `-n N` with a SINGLE-subject prompt.** `-n` runs N generations in parallel and writes `name_1.png … name_N.png`. Do NOT ask the prompt to "explore variations / show options / a few takes" — that makes the model pack a **contact-sheet/grid into one image**. Say "a SINGLE centered X, NOT a grid, not a montage" and let `-n` create the variety.
- **`-i FILE` edits that image (image-to-image); it stays CLOSE to the input.** Use it to iterate on a chosen result ("same icon, thicker strokes"). For *related but freely varied* results, pass the image as a **reference after the prompt** (`genimg "new layout, same palette" ref.png`) instead — it guides style, not composition.
- **Review candidates with `-g --open`** (when `-n ≥ 2`): writes an HTML grid and opens it in the browser. Best way to let a human pick. The grid embeds generation metadata (collapsible prompt + a per-line panel: model, params, single cost) and offers both a grid and a carousel view.
  - **Open without stealing focus (macOS):** `--open` raises the browser to the foreground. To load it in the background instead, drop `--open` and run `open -g <grid.html>` yourself (the CLI prints the grid path). Good when the user is mid-task and doesn't want focus yanked.
- **Model choice:** default `oai:gi2` (gpt-image-2) — best for legible in-image **text, glyphs, logos, UI**. `-m gdm:nbp` (Gemini 3 Pro) — best for **photographic / painterly quality**. `genimg models` lists all.
- **Quality/size (OpenAI):** `-q high` is crisp but 30–90s/image (fine with `-n`, it's parallel); `-q medium` (default) is good for exploration. `-a` aspect (`1:1 3:4 4:3 9:16 16:9`), `-r` resolution (`1K 2K 4K`).
- **Iterate, don't restart:** once a candidate is close, `-i` it with a small instruction rather than regenerating from scratch. The `genimg-agent-refinement` skill is a structured polish loop for this.
- **Cost:** `genimg cost` / `genimg history`. `-q high` + big `-n` adds up (~$0.05–0.21/image).

## Reviewing & sharing results with a human
- **Show before you ask.** When the user has to choose, OPEN/READ the candidates first and let them look — don't lead with a "which do you want?" prompt before anything is on screen (a premature pick-one question just gets rejected). Build a quick contact-sheet or per-section carousel HTML when there are many variants/families to wade through.
- **Hand back a clickable link.** Any local HTML you open, also give as a markdown `file://` hyperlink — `[grid.html](file:///abs/path/grid.html)` — the user routinely wants to reopen it themselves.
- **For the Claude Code preview panel, embed images as base64.** The Launch preview sandboxes the page, so `<img src="sibling.png">` (relative path) renders blank. Inline PNGs as `data:image/png;base64,…` to make it self-contained. A normally-opened browser tab loads relative paths fine — this only bites in the preview panel.
- **Crop/clean a chosen PNG with Pillow.** To trim negative space or drop a baked-in title, scan rows for the first/last with dark pixels (`r/g/b < ~210`) and crop to that ± a margin — don't trust `getbbox()`, anti-aliased near-white edges defeat it.

## Recipes

```bash
# Explore options for a human to pick (4 takes + grid + open).
genimg "a SINGLE centered editorial illustration of a sprint board, flat vector, off-white bg, NOT a grid" -n 4 -g --open -a 16:9

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
- Exploring → `-n 4 -g --open`; never run parallel shell jobs as a substitute for `-n N`, and **vary styles across prompts** (photorealistic, illustrated, cartoony, sketch, minimalist) to find the right register in round 1, not round 2.
- Legible text/logo → `oai:gi2`. Photographic quality → `gdm:nbp`. `-q`/`--quality` is **oai:gi2 only** — the CLI rejects it on gdm models, so omit it there.
- When a human must review, generate to a real `-o` path and `--open` the grid; don't describe images you can't show — open or read them.
