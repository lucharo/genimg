# Maintaining the model list

Model support is intentionally **almost separate from the tool's mechanics**. Provider
dispatch is structural (by model-id shape), so most new models need **no code change**.

## How a model id resolves

`registry.resolve(name)` tries three tiers, in order:

1. **Alias chain** — `gdm:nb2` → `ModelSpec(...)`. Curated, with a short name.
2. **Registered bare id** — `gpt-image-2` reverse-looked-up to its curated spec.
3. **Signature inference** (`registry._infer_spec`) — a well-formed but *unregistered* id
   is dispatched by its prefix:
   - `gpt-image-*` → OpenAI
   - `gemini-*…image…` → Google, region `global`

   (`dall-e-*` is intentionally not inferred — the OpenAI provider only speaks the
   gpt-image request shape, so a DALL-E id would resolve then fail at generation.)

So **a brand-new same-signature model just works** via its full id:

```bash
genimg "a robot" -m gemini-4.0-flash-image -o out.png   # no registry entry needed
```

Inference also absorbs GA-vs-preview id drift: a legacy preview id still resolves by
shape. Curated aliases should point at the serving stable id, confirmed with one direct
generation — `models.list()` can continue advertising a preview id after generation returns 404.

## When to actually edit the registry

Only add an entry when you want one of the things inference *can't* give you:

- a **short alias** (`gdm:nb2` instead of the full id),
- a **`quality_rank`** so it sorts sensibly in `genimg models`,
- a **pinned Vertex region** other than the inferred default.

If none of those matter, skip it — the model already works.

A **cost estimate** is *not* a reason to touch the registry: `cost.py` is keyed by model
id independently, so you can price any id (registered or inferred) by adding a cost row alone.

## Edit recipe

1. **`src/genimg/registry.py`** — add to `_REGISTRY`:
   ```python
   "gdm:<short>":  ModelSpec("google", "<model-id>", region="global", quality_rank=<0-10>),
   "gdm:<nice-name>": "gdm:<short>",   # optional descriptive alias
   ```
   (`ModelSpec(provider, model_id, region=None, quality_rank=5)`; `region` is Google-only.)

2. **The provider's `price()`** — Google: a per-image row in its table. OpenAI GPT Image
   2 / 2.5 (dated snapshots included) are priced from `_TOKEN_GRID` by `token_family()` in
   `providers/openai.py`; a new family needs its token-edge grid from OpenAI's calculator
   script, an older model a size-keyed row in `_LEGACY_PER_IMAGE`. Optional; an unpriced
   model shows `unknown`, stores a JSON `null`, and is excluded from spend totals.

3. Add a resolve test in `tests/test_registry.py`.

For model-specific capabilities, update the provider's `capabilities()` (and `quality_options()` for OpenAI);
the CLI and Draw Studio share it. GPT Image 2.5 Sunburst and Flare (including dated
snapshots) add `xhigh` and `max`; older GPT Image models stop at `high`.
Both families are priced from [OpenAI's calculator](https://developers.openai.com/api/docs/guides/image-generation#calculating-costs)
grid at the [$30 per million output-token rate](https://developers.openai.com/api/docs/pricing);
2.5 has its own, cheaper grid, so never reuse GPT Image 2's numbers for it. When OpenAI
changes the calculator, re-read the `/_astro/GptImageTokenCalculator.react.<hash>.js`
script linked from the guide and re-run `tests/test_cost.py` against fresh `usage` fields.

## Where to check for new models + pricing

- **Google**: <https://ai.google.dev/gemini-api/docs/image-generation> (ids),
  <https://ai.google.dev/gemini-api/docs/pricing> (per-image price).
- **OpenAI**: <https://developers.openai.com/api/docs/models> (ids),
  the image-generation guide for pricing.

## Detecting drift programmatically (dev snippet)

`models.list()` is free and already wired into `discovery.py`. Its results are advertised,
not serving proof; confirm a candidate with one exact-model generation. To list model ids
your credentials advertise that are **not** in the registry (paste into `uv run python -`):

```python
from genimg.auth import openai as ao, google as ag
from genimg.discovery import _listed_model_ids
from genimg.registry import all_canonical

registered = {s.model_id for s in all_canonical().values()}
for name, client in [("openai", ao.get_client()), ("google", ag.get_client())]:
    listed = _listed_model_ids(client.models.list())
    imageish = {m for m in listed if "image" in m.lower()}
    print(name, "unregistered:", sorted(imageish - registered))
```

Caveat: on **Vertex**, `models.list()` may not enumerate Model Garden publisher models,
so this can under-report there (direct APIs are reliable).

## Known caveats to reconcile

- **GA vs `-preview` ids**: provider catalogs can continue advertising a preview id after
  generation has moved to the GA id. Keep curated aliases on the exact id that succeeds in a
  direct generation; signature inference still accepts legacy same-shape ids.
- **Cost rows are approximate and drift**: they track *standard* (non-batch) per-image
  pricing at a ~1K basis and are labelled estimates. Refresh from the pricing page when a
  provider changes prices.
