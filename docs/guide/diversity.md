# Diverse images

`--num 4` asks for four images:

```bash
genimg "a SINGLE minimal fox logo, NOT a grid" \
  --model gdm:nb2 \
  --num 4 \
  --grid
```

<figure markdown>
  ![Four near-identical line-art fox logos](../assets/fox-plain-n.webp){ width="720" }
  <figcaption>On a simple subject the four come back nearly identical.</figcaption>
</figure>

Two flags spread them out.

## Name the styles: `--deltas`

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
It works on every provider. Use it for diagrams and photos too.

## Let genimg pick: `--diverse`

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

`--diverse` picks deltas from a built-in pool that suits illustrations and logos, so each run differs.
On Gemini, `--mode batch` sends one request instead and the model varies its own takes:

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
- `--mode batch` is Gemini only. On OpenAI genimg rejects it, because batched takes come back as
  near-duplicates.
- `--deltas` and `--mode batch` do not combine.
- `--grid --open` opens the set in the [grid](../visual-tools/grid.md), with each card's delta under it.
  A `--mode batch` set has no per-card deltas; its info panel says model-diversified instead.
- Found a winner? Edit it with `--input` ([Input and reference images](input-images.md)).
