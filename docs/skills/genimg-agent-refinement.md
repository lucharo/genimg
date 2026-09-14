# genimg-agent-refinement

An optional polish loop for generated images. The agent shows you the best initial result
first, then offers one artifact-cleanup pass; it never runs extra rounds on its own because an
image "could be better". Use it when you ask to refine, polish, validate or clean up an image,
or when artifacts are obvious and you want a concrete next step.

## The loop

1. Generate a small batch, usually `genimg "PROMPT" -n 4 -g`.
2. Inspect the PNGs at full resolution. For diagrams, dense text and multi-cell layouts the
   agent crops the regions that matter and reads them; a thumbnail hides skipped cells,
   garbled labels, wrong arrow directions and prompt text that leaked in as a label.
3. Pick the strongest candidate.
4. Rewrite the prompt only to remove clear defects.
5. With your approval, re-run once or twice, passing the best prior image as a reference or
   editing it with `-i`.

## What it fixes, and what it leaves alone

Fixed: garbled, duplicated or colliding text; extra labels, axes or decorative junk; missing
requested elements; cropped elements; repeated structures; stray hatching or shadows in flat
areas; broken layout logic in diagrams, maps, mockups and posters.

Left alone: taste. No warmer tones, more whitespace or a "better vibe" unless you asked for
curation.

## Regression rule

The refined prompt names what to keep before what to remove. If a retry fixes one defect but
loses important content, the agent recommends the earlier image and says why in one line.

Read the skill: [skills/genimg-agent-refinement/SKILL.md](https://github.com/lucharo/genimg/blob/main/skills/genimg-agent-refinement/SKILL.md).
