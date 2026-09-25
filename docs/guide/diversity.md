# Diverse images

Sometimes you want several different images for one prompt. `-n` asks for several:

```bash
genimg "a minimal fox logo" -m oai:gi2 -n 4 -g --open
```

Because of the randomness of autoregressive models, the four will be slightly different from
each other, but not very different. For simple subjects (logos, icons, single objects) plain
`-n` converges on near-duplicates.

If you are looking for a particular image with quite notable differences, there are two ways
of doing it. Pick by intent; they are different tools, not better or worse.

## Name the styles yourself: `--deltas`

You explicitly define the directions. Take `#1` keeps the base prompt as the anchor, and
takes `#2..#n` each get one of your deltas in order, so supply `n-1` of them:

```bash
genimg "a minimal fox logo, NOT a grid" -m oai:gi2.5-flare -n 4 \
  --deltas "line art, block print, brush stroke" -g --open
genimg "…" -m oai:gi2.5-flare -n 5 --deltas @styles.txt      # one delta per line
```

`--deltas` implies `-d`. It works on every provider and is the right choice when you know how
the takes should differ, or when the subject is a diagram or photo where the built-in pool
would be a poor fit.

<figure markdown>
  ![Four fox logos: base prompt, line art, block print, brush stroke](../assets/fox-deltas.webp){ width="720" }
  <figcaption>The four takes from the command above with <code>-m oai:gi2.5-flare</code>: #1 is the base prompt, #2 to #4 got one delta each.</figcaption>
</figure>

## Let genimg or the model spread them: `-d`

`-d` (`--diverse`) asks for deliberate variety without you naming it. It behaves differently
by provider:

=== "Gemini models (`gdm:`)"

    Gemini can reason over a batch and generate multiple images at once. With `--mode batch`,
    genimg sends **one** request asking for `n` deliberately different takes and the model
    differentiates palettes, compositions and techniques itself:

    ```bash
    genimg "a minimal fox logo, NOT a grid" -m gdm:nb2 -n 4 -d --mode batch -g --open
    ```

    Slower than parallel (one request instead of four) but the most coherent varied set. The
    model may return fewer than `n`; partial results are kept with a warning. Without
    `--mode batch`, `-d` on Gemini uses the parallel mechanism below.

=== "GPT Image models (`oai:`)"

    GPT Image generates one image at a time, and a batched request returns near-duplicate
    independent samples, so genimg rejects `--mode batch` on OpenAI as wasted spend. `-d`
    runs `n` parallel requests and gives takes `#2..#n` a distinct style or composition delta
    from a curated built-in pool:

    ```bash
    genimg "a minimal fox logo, NOT a grid" -m oai:gi2 -n 4 -d -g --open
    ```

    The pool suits illustrations and logos; for diagrams or photos prefer `--deltas`.

The deltas used are recorded in the metadata sidecar and shown under each card in the
[grid](../surfaces/grid.md), so you can see which direction produced which image.

## Rules of thumb

- Both mechanisms need `-n >= 2`.
- `--deltas` and `--mode batch` do not combine: under batch the model does its own
  differentiation, so pick one path.
- Add `-g --open` to review the set in a grid with a carousel and copy-the-winner buttons.
- Once you have a winner, iterate on it with `-i` (see [Input and reference images](input-images.md))
  rather than regenerating from scratch.
