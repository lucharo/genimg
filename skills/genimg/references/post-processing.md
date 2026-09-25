# Post-processing generated images

- **Crop with Pillow by scanning rows** for the first and last dark pixels (`r/g/b < ~210`), plus a margin. `getbbox()` fails on anti-aliased near-white edges.
- **Solidify after background-key matting.** Keying out a background by colour distance turns pale subject pixels semi-transparent and leaves interior holes that hide at thumbnail size. Flood-fill transparency from the border to find the truly external pixels, fill interior holes with the nearest opaque colour, and snap body alpha ≥ ~90 to 255. Verify at 2× zoom on the flagged region and by counting alpha pixels before and after.
- **Slice a sprite sheet by alpha column runs, not a fixed grid.** Columns whose alpha never passes the threshold separate irregular sprites (ignore runs under ~30 px). The same per-column coverage profile measures composition flaws before you crop.
- **Embed images as base64 in HTML for the Claude Code preview panel.** The panel sandboxes the page, so a relative `<img src="sibling.png">` renders blank there; inline `data:image/png;base64,…` instead. A normal browser tab loads relative paths fine. For comparing candidates, `genimg grid` already builds the page.
