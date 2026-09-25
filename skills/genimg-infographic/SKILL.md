---
name: genimg-infographic
description: "Turn a text, file, URL or topic into one publication-ready raster infographic with GenIMG. Use when the user asks for an infographic, visual summary, high-density visual guide, 信息图 or 可视化. Skip it for charts whose numbers must plot exactly (draw those in code)."
---

# GenIMG Infographic

Adapted from Jim Liu's `baoyu-infographic` v1.117.4 under the MIT licence. Preserve its layout/style methodology and attribution; use `genimg` for every render.

Load the `genimg` skill before invoking the CLI.

## Rules

- Preserve source statistics, quotes, names, dates and technical terms exactly, and add no new facts.
- Strip credentials, tokens and secrets from source material before writing output files.
- Render with GenIMG. The deliverable is a raster image; SVG, HTML, canvas or CSS art is a different deliverable that needs the user's say-so.
- Correct wrong rendered text by fixing the prompt and regenerating; never paint over the bitmap.
- Save the full final prompt under `prompts/` before generating.

## Output structure

```text
infographic/<topic-slug>/
├── source.<ext>
├── analysis.md
├── structured-content.md
├── refs/                      # only when references were supplied
│   └── 01-ref-<slug>.<ext>
├── prompts/
│   └── infographic.md
├── candidates/                 # only for multi-candidate work
├── iterations/                 # only when regenerating a single candidate
├── infographic.png
├── selection-manifest.md       # whenever more than one render or iteration exists
└── comparison.html             # only for multi-candidate work
```

Use a 2-4 word kebab-case slug. If the directory exists, append `-YYYYMMDD-HHMMSS` rather than overwrite prior work.

## Workflow

### 1. Load preferences

Read the first `EXTEND.md` found:

1. `.genimg/infographic/EXTEND.md`
2. `${XDG_CONFIG_HOME:-$HOME/.config}/genimg/infographic/EXTEND.md`
3. `$HOME/.genimg/infographic/EXTEND.md`

If none exists, use the automatic defaults in `references/config/first-time-setup.md` and continue without creating a file or asking setup questions. When the user asks to change preferences, edit or remove the first matching file; the fields are in `references/config/preferences-schema.md`.

### 2. Analyse the source

Load `references/analysis-framework.md`.

1. Save the supplied text, file, URL content or topic material as `source.<ext>`.
2. If the user supplied reference images, preserve and classify them as `references/reference-images.md` describes.
3. Identify the topic, data type, complexity, tone, audience, language, learning objectives and visual opportunities.
4. Extract critical facts verbatim.
5. Save `analysis.md`.

### 3. Structure the content

Load `references/structured-content-template.md` and write `structured-content.md` containing:

- Title and 1-3 learning objectives.
- Sections with a key concept, verbatim content, visual element and exact labels.
- A consolidated list of statistics, quotes and key terms.
- User-provided design instructions.

### 4. Select automatically

Select one coherent configuration without a question panel, in this priority order:

1. Explicit constraints in the current request.
2. A compatible saved preference.
3. A matching keyword shortcut (table below).
4. Source structure, tone, audience, language and visual density, using the content-type pairings in `references/analysis-framework.md`.

Choose:

- the layout and style from the galleries below (without other signals, `bento-grid` + `craft-handmade`);
- the aspect: `landscape` (`16:9`), `portrait` (`9:16`), `square` (`1:1`) or another ratio the model supports;
- the output language;
- the resolution (`2K` unless the model or output needs another);
- the model, through *Model selection* below;
- one final image, unless the user asked for alternatives.

State the selected configuration in a concise progress update, then continue immediately. Do not present a menu or ask for confirmation unless the user explicitly asks to compare or choose among alternatives. If constraints conflict, preserve source fidelity and legibility, record the trade-off, and proceed with the strongest fit.

### 5. Build the prompt

Load:

- `references/base-prompt.md`
- `references/layouts/<layout>.md`
- `references/styles/<style>.md` for a built-in style, or the configured `prompt_fragment` for a custom style
- `structured-content.md`

Assemble one complete prompt at `prompts/infographic.md`, with reference provenance in its frontmatter and any extracted style or palette traits appended. Pin every required cell, row, arrow, label and metric explicitly. Phrase constraints so they cannot be mistaken for visible labels.

`genimg` treats its whole first argument as prompt text, so the frontmatter would leak into the render as pseudo-labels, and a leading `---` can parse as a flag. Strip it into a variable and pass that to the preflight and every generate call:

```bash
PROMPT=$(awk 'NR==1 && /^---$/{skip=1; next} skip && /^---$/{skip=0; next} !skip' prompts/infographic.md)
```

### 6. Preflight

Run the exact planned command with `--dry-run`, passing only `direct` reference images positionally after the prompt:

```bash
genimg "$PROMPT" [refs...] \
  -m <model> -a <ratio> -r <resolution> \
  -o infographic.png --dry-run
```

Check the model, parameters, output path and estimated cost, and resolve any mismatch. Before a material batch, report the estimated cost (as information, not a request for permission), then render and inspect one candidate at the lowest resolution the exact model and aspect support (OpenAI `16:9` and `9:16` need at least `2K`). A dry-run checks only the local plan and calls no API; `genimg auth --check` proves each Google and OpenAI provider on its fixed canary model and checks only the login for Codex. That first real render is what proves the selected model serves.

### 7. Generate

For one image:

```bash
mkdir -p iterations
genimg "$PROMPT" [refs...] \
  -m <model> -a <ratio> -r <resolution> \
  -o iterations/01-initial.png
```

For alternatives, keep one subject and one information architecture. Write `prompts/style-deltas.txt` with exactly `<count> - 1` subject-specific lines (candidate 1 keeps the base prompt; candidates 2 to `<count>` get the deltas in order), then make one `-n` call:

```bash
mkdir -p candidates
genimg "$PROMPT" [refs...] \
  -m <model> -a <ratio> -r <resolution> \
  -n <count> --deltas @prompts/style-deltas.txt \
  -o candidates/infographic.png
```

Record each candidate's stable ID (`infographic_2`), model, original index, filename and review state in `selection-manifest.md`.

### 8. Inspect and iterate

Open every candidate at full resolution. For dense diagrams, crop and inspect each title, panel, legend, footer and connection path. Check:

- Exact text and numbers.
- Required cells and labels are present once.
- Arrows and spatial relationships follow the prompt.
- No instruction text leaked into the artwork.
- Nothing important is cropped or illegible.

If the structure is wrong, regenerate from a corrected full prompt to a new versioned path such as `iterations/02-corrected-arrows.png`. Use `-i` only for a small cosmetic edit to a selected image, passing the aspect again and writing a new versioned file. Every attempt gets a fresh path and a row in `selection-manifest.md`; flawed candidates stay for comparison. After acceptance, copy the selected file unchanged to `infographic.png`.

For multiple candidates, build the grid and open it for the user before asking them to choose:

```bash
genimg grid <candidate-files...> -o comparison.html --open
```

Done when `infographic.png` passes every check above, or the user has picked it from the grid.

### 9. Report

Report the topic, layout, style, aspect, language, model, resolution, estimated or recorded cost, output paths and any remaining defects. Name the recommended candidate when there is one.

## Model selection

1. Honour a model explicitly named in the current request.
2. Use `preferred_model` from `EXTEND.md` when it currently works; otherwise fall through, and state the substitution.
3. Otherwise run `genimg auth --check` (without `--json`, which skips the live probe) and read `genimg models --json`, then choose:
   - `gdm:nb2` for multi-cell diagrams, arrows, fixed spatial layouts and broad exploration.
   - `gdm:nbp` for painterly or highly illustrative infographics where structure still matters.
   - `oai:gi2` for simple layouts where exact typography and crisp UI treatment dominate.
4. If no suitable configured model serves, stop and explain the available setup path.

Always pass `-m`.

## Keyword shortcuts

A match makes the mapped layout the leading selection, promotes its listed styles, and supplies the default aspect, unless explicit constraints, a compatible saved preference or the source structure require another choice.

| User keyword | Layout | Recommended styles | Default aspect | Prompt notes |
| --- | --- | --- | --- | --- |
| `高密度信息大图` / `high-density-info` | `dense-modules` | `morandi-journal`, `pop-laboratory`, `retro-pop-grid`, `retro-popup-pop` | portrait | — |
| `信息图` / `infographic` | `bento-grid` | `craft-handmade` | landscape | Clean canvas, ample whitespace, no complex background textures; simple cartoon elements and icons only. |

## Layout gallery

| Layout | Best for |
| --- | --- |
| `linear-progression` | Timelines, processes, tutorials |
| `binary-comparison` | A vs B, before/after, pros/cons |
| `comparison-matrix` | Multi-factor comparisons |
| `hierarchical-layers` | Pyramids, priority levels |
| `tree-branching` | Categories, taxonomies |
| `hub-spoke` | Central concept with related items |
| `structural-breakdown` | Exploded views, cross-sections |
| `bento-grid` | Multiple topics and overviews |
| `iceberg` | Surface vs hidden aspects |
| `bridge` | Problem to solution |
| `funnel` | Conversion and filtering |
| `isometric-map` | Spatial relationships |
| `dashboard` | Metrics and KPIs |
| `periodic-table` | Categorised collections |
| `comic-strip` | Narratives and sequences |
| `story-mountain` | Plot structure and tension arcs |
| `jigsaw` | Interconnected parts |
| `venn-diagram` | Overlapping concepts |
| `winding-roadmap` | Journeys and milestones |
| `circular-flow` | Cycles and recurring processes |
| `dense-modules` | High-density, data-rich guides |

## Style gallery

| Style | Description |
| --- | --- |
| `craft-handmade` | Hand-drawn paper craft |
| `claymation` | 3D clay figures and stop-motion |
| `kawaii` | Japanese cute and pastels |
| `storybook-watercolor` | Soft painted and whimsical |
| `chalkboard` | Chalk on black board |
| `cyberpunk-neon` | Neon and futuristic |
| `bold-graphic` | Comic style and halftone |
| `aged-academia` | Vintage science and sepia |
| `corporate-memphis` | Flat vector and vibrant |
| `technical-schematic` | Blueprint and engineering |
| `origami` | Folded paper and geometry |
| `pixel-art` | Retro 8-bit |
| `ui-wireframe` | Grayscale interface mockup |
| `subway-map` | Transit diagram |
| `ikea-manual` | Minimal line art |
| `knolling` | Organised flat-lay |
| `lego-brick` | Toy brick construction |
| `pop-laboratory` | Blueprint grid and lab precision |
| `morandi-journal` | Warm muted doodle journal |
| `retro-pop-grid` | 1970s pop art and Swiss grid |
| `hand-drawn-edu` | Pastel educational drawing |
| `retro-popup-pop` | Vintage UI collage and flat pop colour |

A configured custom style uses its `prompt_fragment` directly, with no style file.
