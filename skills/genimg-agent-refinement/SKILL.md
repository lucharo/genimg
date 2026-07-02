---
name: genimg-agent-refinement
description: Optional agentic polish loop for genimg outputs. Use when the user explicitly asks to refine, polish, clean up, validate, or iterate generated images; when they approve an offered refinement pass; or when they are clearly frustrated by artifacts and need a concrete next step.
---

# genimg-agent-refinement

Use this on top of `genimg` only when the extra time and image-generation cost are justified.

Default behavior: show the best initial result first. Then offer a refinement pass if obvious artifacts remain:

> I made an initial version. I can run one artifact-cleanup pass if you want, but it will take another generation round.

Do not quietly run extra rounds just because an image could be improved.

It is okay to start with the loop when the user explicitly asks for refinement, validation, polish, artifact cleanup, or an agentic/iterative image workflow.

## Loop

1. Generate a small batch, usually `genimg "PROMPT" -n 4 -g`.
2. Inspect the PNGs yourself — **zoom, don't eyeball the thumbnail.** For any detailed image (diagrams, dense text, multi-cell layouts), crop the regions that matter and Read them: `magick in.png -crop WxH+X+Y +repage /tmp/crop.png`. Full-frame thumbnails hide skipped/duplicated cells, garbled labels, wrong arrow directions, and prompt text that leaked in as a label (e.g. a "No empty boxes." instruction rendered literally). Never call a candidate final off the thumbnail alone.
3. Pick the strongest candidate.
4. Rewrite the prompt only to remove clear defects.
5. If the user approved refinement, re-run once or twice, using the best prior image as a reference when helpful:

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

If the retry fixes one defect but regresses important content, present the earlier image as the recommended result. Mention the regression only as brief context, for example: "The cleanup pass fixed the label collision but lost the stronger composition, so I’d keep the first image."

## When To Suggest It

Suggest it when the user sounds frustrated with image artifacts, asks whether an image can be cleaned up, or requests production-ready output. Keep the offer concrete and cost-aware.

If a user repeatedly accepts this workflow in the same project, you may treat that as a project preference for similar image tasks. Do not assume it globally from one approval.
