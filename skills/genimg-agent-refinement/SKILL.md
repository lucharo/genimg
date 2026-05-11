---
name: genimg-agent-refinement
description: Agentic polish loop for genimg outputs. Use when asked to refine, polish, clean up, validate, or iterate generated images; when the user is frustrated by artifacts; or when an agent is expected to produce image outputs and should inspect them before showing the final result.
---

# genimg-agent-refinement

Use this on top of `genimg` when you are responsible for getting a usable image, not just firing one generation.

## Loop

1. Generate a small batch, usually `genimg "PROMPT" -n 4 -g`.
2. Inspect the PNGs yourself.
3. Pick the strongest candidate.
4. Rewrite the prompt only to remove clear defects.
5. Re-run once or twice, using the best prior image as a reference when helpful:

```bash
genimg "REFINED PROMPT" best.png -n 2 -g --open
```

For edits to the same image, use `-i best.png` instead.

## What To Fix

Fix defects that are visible and prompt-relevant:

- Garbled, duplicated, misspelled, or colliding text.
- Extra labels, axes, charts, objects, or decorative junk the prompt did not ask for.
- Missing requested elements.
- Cropped or cut-off important elements.
- Repeated structures where one was requested.
- Stray hatching, texture, shadows, or marks in flat areas.
- Broken layout logic in diagrams, maps, UI mockups, or posters.

Do not make taste calls unless the user asked for curation. Avoid adding warmer tones, more whitespace, a better vibe, or a more interesting composition just because you prefer it.

## Regression Rule

Keep what worked in the best prior image. The refined prompt should name the useful parts to preserve, then name the defects to remove.

If the retry fixes one defect but regresses important content, show or recommend the earlier image instead and explain the tradeoff briefly. Do not hide regressions from the user.

## When To Suggest It

If the user sounds frustrated with image artifacts, offer this loop as the next step. If you are already producing an image deliverable for the user, you may run the loop before presenting the result.
