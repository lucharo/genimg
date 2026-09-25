# Cost, provenance and timing

## Cost

- `--dry-run` prints the estimate for a planned call; `genimg cost` totals estimated spend, and `genimg history` shows it per generation.
- Estimates count output tokens only. At 1024×1024: `oai:gi2` medium $0.053, high $0.211; `oai:gi2.5` medium $0.013, high $0.053, max $0.211. A wide 2K render can cost less than a 1K square: `oai:gi2` medium at 2048×1152 is $0.042.

## Billing and provenance

- Each generation records `billing` (`subscription` or `api`) from its route. `api_equivalent_cost` is a separate, theoretical comparison, and a rough range when the native quality is unknown: report it as a comparison, never as a charge, and keep it out of subscription spend. Unknown models and prices stay unknown.
- genimg captures each image's C2PA claim (extracted offline, not signature-verified), generator, dimensions and hash. PNGs that carry credentials keep their bytes unchanged; genimg's own fields go in sidecar files.

## Timing

One-shot CLI wall time includes local setup and cold start, so it is not provider latency. Record setup time and provider-call time separately, and state which clock each comparison uses.
