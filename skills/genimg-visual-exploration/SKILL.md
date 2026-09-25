---
name: genimg-visual-exploration
description: "Explore deliberately different visual directions with genimg before committing to one, then converge on a winner. Use when the user wants options, concepts or a moodboard for a logo, poster, slide, illustration or hero image before the final is built."
---

# Visual exploration

The divergent phase before a visual is final: find the strongest idea first, and polish it
later. Load `genimg` first; it owns flags, model choice and cost.

## 1. Brief

Before any render, write `brief.md`:

- the one **claim** the visual must leave behind;
- two to four supporting ideas;
- fixed constraints: format and aspect, audience, brand colours, exact wording, what must not appear;
- open variables: metaphor, composition, medium, density.

Keep **concepts** (what it says) apart from **treatments** (how it looks). "Setup takes one
command" is a concept; "a single domino" is one treatment of it. A promising treatment must not
quietly replace the claim.

If the user supplied a sketch and says it already is the concept, its layout is fixed. Skip to
step 5 and make at most two faithful treatments of it.

Done when the claim fits in one sentence and every constraint is written down.

## 2. Directions

Pick three to six directions that differ in metaphor or information structure, beyond colour,
lens or rendering style. For each, note what a viewer grasps in three seconds and what it leaves
out. Write one direction per line in `directions.txt`; `#` lines are comments. They become the
deltas for images #2 to #n, and #1 keeps the base prompt as the anchor.

Done when no two directions would read as the same idea in a different style.

## 3. Generate

Prompt for a SINGLE subject and let `-n` make the variety. Preflight with `--dry-run`, then run
one call per provider:

```bash
genimg "a SINGLE poster about <claim>, NOT a grid, NOT a montage" \
  -m gdm:nb2 -n 5 --deltas @directions.txt -a 16:9 -o explore/gemini.png
genimg "a SINGLE poster about <claim>, NOT a grid" \
  -m oai:gi2 -n 2 --deltas "typography-led layout" -a 16:9 -r 2K -o explore/gpt.png
```

A second provider adds breadth one model cannot; the `genimg` skill says which model suits
text, structure or photographic work. Leave publication-critical text out of the image unless
the exploration is about typography; add exact wording later.

**Stable IDs.** The output stem plus index (`gemini_3`, `gpt_1`) is each candidate's ID. Never
rename or renumber a candidate once someone has seen it; a later round gets a new stem
(`round2-gemini`). Keep `selection-manifest.md` with one row per candidate: ID, direction, model, delta,
status (`new`, `liked`, `rejected`, `winner`).

Inspect every image at full size yourself. Reject garbled text, the wrong subject, a collage of
several images or a direction that says a different idea, and note why in the manifest.

Done when every direction has at least one sound candidate in the manifest.

## 4. Compare

Put every candidate in one grid and show it before asking anything:

```bash
genimg grid explore/gemini_*.png explore/gpt_*.png -o explore/directions.html --open
```

Each card copies `I choose #3 (gemini_3.png)` for the user to paste back. When the user cannot
choose among 3 to 20 candidates, point them at **Tournament** in the grid: two images at a time,
n−1 picks for a winner, one more with **Top 3**. Ask them to paste **Copy result (JSON)**:
`winner` and `ranking` give each image's grid number and file name, and `choices` lists every
pick. Record the result in the manifest.

The tournament ranks whole images. Ask separately which features of the losers are worth
keeping: a palette, a layout, a motif.

Done when the manifest records a winner or a shortlist and the user confirmed it.

## 5. Converge

Write three lists in `selection-manifest.md`: **keep**, **combine**, **reject**. Rejected directions stay
out of later rounds. Then:

- **Recombine** features from several candidates by passing them as references after the prompt,
  naming what each contributes:

  ```bash
  genimg "the layout of the first reference with the palette of the second, a SINGLE poster, NOT a grid" \
    explore/gemini_3.png explore/gpt_1.png -m gdm:nb2 -a 16:9 -o explore/round2.png
  ```

- **Refine** a near-final pick with `-i`: one change per call, stating what must stay:

  ```bash
  genimg "same poster, bolder title; keep the layout and colours" \
    -i explore/gemini_3.png -m gdm:nb2 -a 16:9 -o explore/gemini_3-v2.png
  ```

Run another broad round only when the first one missed a concept from the brief; polish stays
in this step.

## Done when

- `brief.md` names the claim, and the directions differ in idea.
- `selection-manifest.md` lists every candidate by stable ID with a status, plus keep, combine and reject.
- The user chose a direction in the grid or the Tournament, and it was refined or recombined
  until they accepted it.
