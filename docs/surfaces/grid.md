# Grid and carousel

The grid is genimg's review surface: a single self-contained HTML file with every candidate,
its prompt, the delta that produced it, size, cost and provenance. It opens by double-click,
needs no server, and can be sent to someone else as one file.

```bash
genimg "a minimal fox logo" -m oai:gi2 -n 4 -d -g --open   # generate + grid
genimg grid a.png b.png c.png -o review.html --open         # any existing files
```

## What is on the page

- Grid view: all images at once, each card with its number, filename, the prompt delta
  (in diverse mode) and a *copy* button that puts `I choose #3 (fox_3.png)` on the clipboard,
  ready to paste back to an agent.
- Carousel view: one image at a time, keyboard-navigable, for close comparison.
- Prompt panel: the full prompt, collapsible.
- Metadata panel: model, parameters, input and ordered references, per-image cost, the
  reported C2PA generator when an image carries content credentials.

View, prompt visibility and carousel index persist in the URL, so a link to `#carousel-2`
opens on that image.

## Where grids go

With `-g` the grid lands next to the generation in `~/.genimg/grids/<id>.html` and its path is
recorded in the metadata sidecar. `genimg grid` writes to `-o` or a timestamped file in the
same directory. Images are embedded as data URIs, so the file stays valid when the originals
move.

## Cost line

For a generation grid, the cost shown is the CLI's estimate for the run, which knows quality
and size. For `genimg grid` over arbitrary files, no provenance is known and no cost is
claimed.

See also [Draw Studio](draw-studio.md), the canvas surface, and
[Diverse images](../guide/diversity.md) for producing a set worth reviewing.
