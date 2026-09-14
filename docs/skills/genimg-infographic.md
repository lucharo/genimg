# genimg-infographic

Turn source material (a document, a dataset, notes, a transcript) into a publication-ready
raster infographic. The skill chooses one of 21 information layouts (bento grid, comparison
matrix, funnel, hub and spoke, iceberg, winding roadmap, …) and one of 22 visual styles
(chalkboard, IKEA manual, knolling, subway map, technical schematic, storybook watercolor,
…), writes the full prompt to disk, and renders it through genimg.

Adapted from Jim Liu's `baoyu-infographic` under the MIT licence; the layout and style
methodology and attribution are preserved.

## What it does for you

- Analyses the source, extracts the structure, and picks layout, style, aspect ratio,
  language, model and resolution automatically. Routine choices are not put back to you.
- Keeps statistics, quotes, names, dates and technical terms exact, and strips secrets
  before any file is written.
- Saves the final prompt under `prompts/` so a render is reproducible, and records every
  reference image with its usage (`direct`, `style` or `palette`).
- Preflights with `--dry-run` and reports estimated cost before a material batch.
- Uses raster generation only, and fixes rendered text by correcting the prompt and
  regenerating, never by painting over pixels.

## Model choice

`gdm:nb2` for multi-cell diagrams, arrows and fixed spatial layouts; `gdm:nbp` for painterly
or highly illustrative pieces where structure still matters; `oai:gi2` when exact typography
and crisp UI treatment dominate. The skill runs `genimg auth --check` and reads
`genimg models --json` before choosing, and generates one low-resolution candidate before a
batch.

## Try it

Ask your agent for an infographic and point it at the source:

> Make a 16:9 infographic of `docs/onboarding.md` for a new-hire deck; hand-drawn style.

Read the skill: [skills/genimg-infographic/SKILL.md](https://github.com/lucharo/genimg/blob/main/skills/genimg-infographic/SKILL.md),
with the layout and style catalogues under `references/`.
