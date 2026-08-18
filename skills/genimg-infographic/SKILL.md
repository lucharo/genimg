---
name: genimg-infographic
description: "Create publication-ready raster infographics with GenIMG using 21 information layouts and 22 visual styles. Use when the user asks for an infographic, visual summary, information graphic, high-density visual guide, 信息图, 可视化, or wants source material turned into a structured image with readable labels and reproducible prompts."
---

# GenIMG Infographic

Adapted from Jim Liu's `baoyu-infographic` v1.117.4 under the MIT licence. Preserve its layout/style methodology and attribution; use `genimg` for every render.

Load the `genimg` skill before invoking the CLI.

## Non-negotiable rules

- Save the full final prompt under `prompts/` before generation.
- Preserve source statistics, quotes, names, dates, and technical terms exactly.
- Strip credentials, tokens, and secrets from source material before writing output files.
- Select layout, style, aspect, language, model, resolution, and reference usage automatically from the source, explicit user constraints, saved preferences, and live availability. Do not ask the user to confirm routine generation choices.
- Use raster generation. Do not silently substitute SVG, HTML, canvas, or CSS art.
- Never repair rendered text by painting over the bitmap. Correct the prompt and regenerate.
- Preserve every supplied reference and record whether it is used directly, for style, or for palette extraction.
- Preflight paid work with `--dry-run`, then report the estimated cost before a material batch.

## GenIMG model selection

Resolve the model in this order:

1. Honour a model explicitly named in the current request.
2. Use `preferred_model` from `EXTEND.md` when it is currently working.
3. Otherwise run `genimg auth --check` for a live provider-level canary and inspect `genimg models --json`, then choose:
   - `gdm:nb2` for multi-cell diagrams, arrows, fixed spatial layouts, and broad exploration.
   - `gdm:nbp` for painterly or highly illustrative infographics where structure is still important.
   - `oai:gi2` for simple layouts where exact typography and crisp UI treatment dominate.
4. If no suitable configured model serves, stop and explain the available setup path.

Always pass `-m`. A model listed in the catalogue is advertised, not proven serving, and `genimg auth --check` proves only its fixed provider canaries. The first real generation with the selected model is the exact-model canary. For a material batch, generate and inspect one candidate at the lowest resolution supported by that exact model and aspect before launching the rest. Do not combine `--check` with `--json`: GenIMG's JSON auth view reports configuration and cached inventory but does not execute the live probe.

## Reference images

Accept reference files supplied in the request and copy each one into the output directory as `refs/NN-ref-<slug>.<ext>` so the prompt remains reproducible. GenIMG accepts direct references as positional file arguments; it has no `--ref` option.

Assign one usage mode per reference:

| Usage | Effect |
| --- | --- |
| `direct` | Pass the preserved file positionally to GenIMG for composition, subject, or close visual guidance |
| `style` | Describe its line treatment, texture, lighting, and mood in the prompt; do not pass the file |
| `palette` | Extract and record representative hex colours in the prompt; do not pass the file |

Record reference provenance in `prompts/infographic.md` frontmatter:

```yaml
references:
  - ref_id: 01
    filename: refs/01-ref-brand.png
    usage: direct
```

Verify every preserved file before generation. Only `direct` references appear as positional CLI arguments. When the user has not specified a mode, infer it from their stated intent and record the choice in the prompt frontmatter.

## Options

| Option | Values |
| --- | --- |
| Layout | 21 layouts; default recommendation `bento-grid` |
| Style | 22 styles; default recommendation `craft-handmade` |
| Aspect | `landscape` (16:9), `portrait` (9:16), `square` (1:1), or a supported custom ratio |
| Language | `en`, `zh`, `ja`, etc. |
| Model | GenIMG alias such as `gdm:nb2`, `gdm:nbp`, or `oai:gi2` |
| Resolution | `1K`, `2K`, or `4K`; default recommendation `2K` |
| Candidates | One final by default; use a controlled multi-candidate run only when requested or useful for selection |

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

Load the selected definition from `references/layouts/<layout>.md`.

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

For a built-in style, load `references/styles/<style>.md`. For a configured custom style, use its `prompt_fragment` directly and do not resolve a built-in style file.

## Recommended combinations

| Content | Layout and style |
| --- | --- |
| Timeline/history | `linear-progression` + `craft-handmade` |
| Step-by-step | `linear-progression` + `ikea-manual` |
| A vs B | `binary-comparison` + `corporate-memphis` |
| Hierarchy | `hierarchical-layers` + `craft-handmade` |
| Overlap | `venn-diagram` + `craft-handmade` |
| Conversion | `funnel` + `corporate-memphis` |
| Cycles | `circular-flow` + `craft-handmade` |
| Technical | `structural-breakdown` + `technical-schematic` |
| Metrics | `dashboard` + `corporate-memphis` |
| Educational | `bento-grid` + `chalkboard` |
| Journey | `winding-roadmap` + `storybook-watercolor` |
| Categories | `periodic-table` + `bold-graphic` |
| Product guide | `dense-modules` + `morandi-journal` |
| Technical guide | `dense-modules` + `pop-laboratory` |
| Trendy guide | `dense-modules` + `retro-pop-grid` |
| Retro pop guide | `dense-modules` + `retro-popup-pop` |
| Educational diagram | `hub-spoke` + `hand-drawn-edu` |
| Process tutorial | `linear-progression` + `hand-drawn-edu` |

## Keyword shortcuts

Check these before content-based layout inference. A match makes the mapped layout the leading selection, promotes its listed styles, and supplies the default aspect unless explicit user constraints, a compatible saved preference, or source structure require another choice.

| User keyword | Layout | Recommended styles | Default aspect | Prompt notes |
| --- | --- | --- | --- | --- |
| `高密度信息大图` / `high-density-info` | `dense-modules` | `morandi-journal`, `pop-laboratory`, `retro-pop-grid`, `retro-popup-pop` | portrait | — |
| `信息图` / `infographic` | `bento-grid` | `craft-handmade` | landscape | Clean canvas, ample whitespace, no complex background textures; simple cartoon elements and icons only. |

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
└── comparison.html           # only for multi-candidate work
```

Use a 2-4 word kebab-case slug. If the directory exists, append `-YYYYMMDD-HHMMSS`; do not overwrite prior work.

## Workflow

### 1. Load preferences

Read the first `EXTEND.md` found:

1. `.genimg/infographic/EXTEND.md`
2. `${XDG_CONFIG_HOME:-$HOME/.config}/genimg/infographic/EXTEND.md`
3. `$HOME/.genimg/infographic/EXTEND.md`

If none exists, use the automatic defaults in `references/config/first-time-setup.md` and continue without creating a file or asking setup questions. Preferences guide automatic selection when present.

### 2. Analyse the source

Load `references/analysis-framework.md`.

1. Save the supplied text, file, URL content, or topic material as `source.<ext>`.
2. Preserve supplied reference images under `refs/`, assign their `direct`, `style`, or `palette` usage, and record the reasoning.
3. Identify the topic, data type, complexity, tone, audience, language, learning objectives, and visual opportunities.
4. Extract critical facts verbatim.
5. Save `analysis.md`.

### 3. Structure the content

Load `references/structured-content-template.md` and write `structured-content.md` containing:

- Title and 1-3 learning objectives.
- Sections with a key concept, verbatim content, visual element, and exact labels.
- A consolidated list of statistics, quotes, and key terms.
- User-provided design instructions.

Do not introduce new facts.

### 4. Select automatically

Apply a matching keyword shortcut first; otherwise infer from the content. Select one coherent configuration without a question panel, in this priority order:

1. Explicit constraints in the current request.
2. Compatible saved preferences.
3. A matching keyword shortcut.
4. Source structure, tone, audience, language, and visual density.

Choose the layout/style pair, aspect ratio, output language, resolution, and reference usage modes. Resolve the model through the live model-selection rules above. State the selected configuration in a concise progress update, then continue immediately; cost reporting before a material batch is informational, not a request for permission. If constraints conflict, preserve source fidelity and legibility, record the trade-off, and proceed with the strongest fit.

Do not present a menu or ask for confirmation unless the user explicitly asks to compare or choose among alternatives. When alternatives are requested, keep one information architecture and generate controlled candidates for selection.

### 5. Build the prompt

Load:

- `references/base-prompt.md`
- `references/layouts/<layout>.md`
- `references/styles/<style>.md` for a built-in style, or the configured `prompt_fragment` for a custom style
- `structured-content.md`

Assemble one complete prompt at `prompts/infographic.md`. Include reference provenance frontmatter, append extracted style/palette traits, and pin every required cell, row, arrow, label, and metric explicitly. Phrase constraints so they cannot be mistaken for visible labels.

Map named aspects to CLI ratios: `landscape` → `16:9`, `portrait` → `9:16`, `square` → `1:1`.

### 6. Preflight GenIMG

Run the exact planned command with `--dry-run`. Use the saved prompt as one shell argument and pass only `direct` reference images positionally after it:

```bash
genimg "$(<prompts/infographic.md)" [refs...] \
  -m <model> -a <ratio> -r <resolution> \
  -o infographic.png --dry-run
```

Read the model, parameters, output path, and estimated cost. Resolve any mismatch before the real call.

For a material batch, first render one candidate at the lowest resolution compatible with the exact selected model and aspect, then inspect it. For example, OpenAI 16:9 and 9:16 require at least 2K. A successful provider auth probe or dry-run does not prove that model serves. The normal single-image generation is itself the exact-model canary.

### 7. Generate

For one image:

```bash
mkdir -p iterations
genimg "$(<prompts/infographic.md)" [refs...] \
  -m <model> -a <ratio> -r <resolution> \
  -o iterations/01-initial.png
```

For controlled alternatives, keep one subject and one information architecture. Before generation, write `prompts/style-deltas.txt` with at least `<count> - 1` non-empty, subject-specific lines; candidate 1 keeps the base prompt and candidates 2 through `<count>` receive those deltas in order. Then use one `-n` call, not a prompt asking the model to draw a contact sheet:

```bash
mkdir -p candidates
genimg "$(<prompts/infographic.md)" [refs...] \
  -m <model> -a <ratio> -r <resolution> \
  -n <count> --deltas @prompts/style-deltas.txt \
  -o candidates/infographic.png
```

Record stable candidate IDs, model, original index, filename, and review state in `selection-manifest.md`.

### 8. Inspect and iterate

Open every candidate at full resolution. For dense diagrams, crop and inspect each title, panel, legend, footer, and connection path. Check:

- Exact text and numbers.
- Required cells and labels are present once.
- Arrows and spatial relationships follow the prompt.
- No instruction text leaked into the artwork.
- Nothing important is cropped or illegible.

If structure is wrong, regenerate from a corrected full prompt to a new versioned path such as `iterations/02-corrected-arrows.png`; never reuse an existing output path. Use `-i` only for a small cosmetic edit to a selected image, always passing the aspect again and writing a new versioned file. Record every attempt and disposition in `selection-manifest.md`. After acceptance, copy the selected file unchanged to `infographic.png`. Preserve flawed candidates for comparison.

For multiple candidates:

```bash
genimg grid <candidate-files...> -o comparison.html
```

Open the grid for the user before asking them to choose.

### 9. Report

Report the topic, layout, style, aspect, language, model, resolution, estimated/recorded cost, output paths, and any remaining defects. Name the recommended candidate when there is one.

## Changing preferences

Edit or remove the first matching `EXTEND.md`. Common values:

- `preferred_model: auto` to choose from live GenIMG models.
- `preferred_model: gdm:nb2` for structured diagrams.
- `preferred_model: oai:gi2` for simple text-led layouts.
- `preferred_resolution: 2K` for normal final output.
- `preferred_layout`, `preferred_style`, `preferred_aspect`, and `language` to shift recommendations.

Full schema: `references/config/preferences-schema.md`.
