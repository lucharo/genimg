# Diverse images

- `--num 4` makes four images at once: four requests run in parallel, so four usually take about
  as long as one. `codex:image` runs two at a time, so four take two rounds.
- On a simple subject, plain `--num 4` returns four near-copies.
- `--deltas` or `--diverse` makes each take look different.

```bash
genimg "a SINGLE minimal fox logo, NOT a grid" \
  --model gdm:nb2 \
  --num 4 \
  --grid
```

<figure markdown>
  ![Four near-identical line-art fox logos](../assets/fox-plain-n.webp){ width="720" }
  <figcaption>Plain <code>--num 4</code>.</figcaption>
</figure>

## Name the styles: `--deltas`

- You choose the look of each take, on any provider and any subject.

```bash
genimg "a minimal fox logo, NOT a grid" \
  --model oai:gi2.5-flare \
  --num 4 \
  --deltas "line art, block print, brush stroke" \
  --grid \
  --open
```

<figure markdown>
  ![Four fox logos: base prompt, line art, block print, brush stroke](../assets/fox-deltas.webp){ width="720" }
  <figcaption>Take #1 keeps the base prompt. Takes #2 to #4 get one delta each, in order.</figcaption>
</figure>

Pass one delta fewer than `--num`, comma-separated or as `--deltas @styles.txt` with one per line.

## Let genimg pick: `--diverse`

- No styles in mind? genimg picks a different look for each take, and each run differs.

```bash
genimg "a SINGLE minimal fox logo, NOT a grid" \
  --model gdm:nb2 \
  --num 4 \
  --diverse \
  --grid \
  --open
```

<figure markdown>
  ![Four varied fox logos: a wordmark, a copper close-up, a neon sign, a white cut-out on slate](../assets/fox-diverse.webp){ width="720" }
  <figcaption>Takes #2 to #4 drew close-up framing, neon glow and dramatic lighting from the built-in pool.</figcaption>
</figure>

The built-in pool suits illustrations and logos.

## Let the model pick: `--mode batch` (Gemini)

- One request asks Gemini for the whole set, so the model sees every take and makes them differ
  as a set, instead of genimg adding a style to each.
- The model decides how many images to return, so you may get fewer than `--num`; the default
  parallel mode returns `--num` images unless a request fails.

```bash
genimg "a minimal fox logo, NOT a grid" \
  --model gdm:nb2 \
  --num 4 \
  --diverse \
  --mode batch \
  --grid \
  --open
```

## Rules of thumb

- Both need `--num 2` or more.
- Parallel mode runs up to five requests at a time (two for `codex:image`), and keeps the images
  that succeed if one fails.
- `--mode batch` is Gemini only. On OpenAI genimg rejects it, because batched takes come back as
  near-duplicates.
- `--deltas` and `--mode batch` do not combine.
- `--grid --open` opens the set in the [grid](../visual-tools/grid.md), with each card's delta under it.
  A `--mode batch` set has no per-card deltas; its info panel says model-diversified instead.
- Found a winner? Edit it with `--input` ([Input and reference images](input-images.md)).
