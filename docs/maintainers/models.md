# Adding or updating a model

Most new models need no code change. genimg resolves `--model` in this order:

1. A curated alias in `registry.py`, such as `gdm:nb2`.
2. A model id already in the registry, such as `gpt-image-2`.
3. Any id a provider recognises by shape: `gpt-image-*` goes to OpenAI, `gemini-*image*` to Google.

So a new model works straight away with its full id:

```bash
genimg "a robot" --model gemini-4.0-flash-image
```

## When to edit the registry

Add an entry only for a short alias, a `quality_rank` so it sorts well in `genimg models`, or a
fixed Vertex region. Point the alias at the stable id that succeeds in a real generation. Provider
listings can keep advertising a `-preview` id after it stops serving.

## Steps

1. Add the entry to `_REGISTRY` in `src/genimg/registry.py`:

    ```python
    "gdm:<short>": ModelSpec("google", "<model-id>", region="global", quality_rank=8),
    ```

2. Add a price if you want cost estimates. Google prices live in `_PER_IMAGE` in
   `providers/google.py`. GPT Image 2 and 2.5 use token grids in `_TOKEN_GRID` in
   `providers/openai.py`, copied from
   [OpenAI's cost calculator](https://developers.openai.com/api/docs/guides/image-generation);
   older OpenAI models use `_LEGACY_PER_IMAGE`. An unpriced model shows `unknown`.
3. If the model takes different sizes or qualities, update the provider's `capabilities()`, and
   `quality_options()` for OpenAI. The CLI and Draw Studio both read them.
4. Add a resolve test in `tests/test_registry.py`, and a price test in `tests/test_cost.py`.

## Finding new models

Check the provider pages: Google
[models](https://ai.google.dev/gemini-api/docs/image-generation) and
[pricing](https://ai.google.dev/gemini-api/docs/pricing), OpenAI
[models](https://developers.openai.com/api/docs/models) and
[pricing](https://developers.openai.com/api/docs/pricing).

To list image models your credentials can see that the registry lacks, run this with
`uv run python -`:

```python
from genimg.auth import google, openai
from genimg.providers.listing import listed_model_ids
from genimg.registry import all_canonical

known = {s.model_id for s in all_canonical().values()}
for name, client in [("openai", openai.get_client()), ("google", google.get_client())]:
    listed = listed_model_ids(client.models.list())
    new = {m for m in listed if "image" in m and "/" not in m} - known
    print(name, sorted(new))
```

Output on 25 September 2026, with Azure OpenAI and a Gemini API key:

```text
openai ['gpt-image-1-2025-04-15', 'gpt-image-1-mini-2025-10-06', 'gpt-image-1.5-2025-12-16', 'gpt-image-2-2026-04-21', 'gpt-image-2.5-flare-2026-09-08', 'gpt-image-2.5-sunburst-2026-09-08']
google ['gemini-3-pro-image-preview', 'gemini-3.1-flash-image-preview']
```

Dated snapshots and `-preview` ids like these already resolve by shape, so they need no entry. On
Vertex, the listing can omit Model Garden models.
