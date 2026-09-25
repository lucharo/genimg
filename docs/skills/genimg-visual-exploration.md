# genimg-visual-exploration

Several genuinely different directions first, then the one you pick.

> Explore a few directions for a launch poster about one-command setup.

1. **Brief.** The agent writes down the one claim the visual must make and what is fixed.
2. **Directions.** Three to six ideas that differ in metaphor or layout, beyond colour.
3. **Generate.** One `--num` run per provider with your directions as `--deltas`. Each image keeps
   a stable ID such as `gemini_3`.
4. **Compare.** Every candidate in one [grid](../visual-tools/grid.md). Can't decide? Run its
   **Tournament** and paste back the result.
5. **Converge.** The agent recombines features with reference images, or refines the pick
   with `--input`.

```bash
genimg "a SINGLE poster about <claim>, NOT a grid" \
  --model gdm:nb2 \
  --num 5 \
  --deltas @directions.txt \
  --output explore/gemini.png
genimg grid explore/*.png \
  --output explore/directions.html \
  --open
```

[Read the skill](https://github.com/lucharo/genimg/blob/main/skills/genimg-visual-exploration/SKILL.md).
