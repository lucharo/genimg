# Model-specific options

- **Gemini can return a whole set in one request** with `--mode batch`.
- **Gemini 3.1 can think harder before it draws** with `--thinking high`.
- **Gemini can reply with text.** genimg prints it but does not save it.
- **Only GPT Image 2.5 has `xhigh` and `max` quality.**
- **Codex picks the model and size for you.** `--aspect-ratio` is only a request.

`--num`, `--diverse`, `--deltas`, `--output` and `--grid` work with every model. genimg rejects a
flag the model can't use, even on `--dry-run`.

| Flag | Gemini (`gdm:`) | OpenAI (`oai:`) | Codex (`codex:image`) |
| --- | --- | --- | --- |
| `--mode batch` | ✅ | ❌ | ❌ |
| `--thinking` | ✅ `gdm:nb2`, `gdm:nb2-lite` only | ❌ | ❌ |
| `--quality` | ❌ | ✅ `xhigh`, `max` on 2.5 only | ❌ |
| `--resolution` | ✅ [by model](models.md#gemini) | ✅ [size table](models.md#openai), `1K` only on GPT Image 1.x | ❌ |
| `--aspect-ratio` | ✅ 10 ratios, 14 on `gdm:nb2`, `gdm:nb2-lite` | ✅ 5 ratios, `1:1` only on GPT Image 1.x | ✅ as a prompt request |
| `--input`, reference images | ✅ | ✅ up to 16 files | ✅ |
| `--region` | ✅ | ❌ | ❌ |
| `--project` | ✅ | ❌ | ❌ |
| `--auth` | ❌ | ✅ `azure` or `direct` | ❌ |
| Text reply | ✅ printed, not saved | ❌ | ❌ dropped |

## Gemini

- **With `--mode batch --diverse`, the model varies its own takes.** See
  [Diverse images](../guide/diversity.md).
- **A batch can come back short.** The model picks the count. genimg keeps what arrives and warns.
- **`--thinking high` costs more than the estimate.** Google bills thinking tokens, and genimg leaves
  them out.
- **Only text before the image is printed.** genimg drops the rest, and all text in batch mode.

```console
$ genimg "a minimal fox logo" \
    --model gdm:nb2 \
    --num 4 \
    --diverse \
    --mode batch \
    --thinking high \
    --dry-run
genimg google/direct gdm:nb2 → gemini-3.1-flash-image
  prompt   "a minimal fox logo"
  params   n=4 mode=batch diverse thinking=high
  cost     $0.2680 (estimate)  id=20260925_115942_6af52e
  outputs  ~/.genimg/generations/20260925_115942_6af52e_1.png
           …
  diverse  model-coordinated: the single batched request asks for deliberately different takes
dry-run: no API call made.
```

## OpenAI

- **`--quality` defaults to `medium`.** GPT Image 2.5 adds `xhigh` and `max`.
- **`--num` sends one request per image.** A batch returns near-duplicates, so genimg rejects it.
- **GPT Image 1, 1.5 and 1 mini take 1024×1024 only.**
- **Up to 16 input and reference images.** PNG, JPEG or WebP, 50 MB each.

```console
$ genimg "a lighthouse at dusk" \
    --model oai:gi2.5 \
    --quality xhigh \
    --resolution 2K \
    --aspect-ratio 16:9 \
    --dry-run
genimg openai/direct oai:gpt-image-2.5-sunburst → gpt-image-2.5-sunburst
  prompt   "a lighthouse at dusk"
  params   n=1 q=xhigh r=2K a=16:9 → 2048x1152
  cost     $0.0753 (estimate)  id=20260925_115943_ca5e9a
  output   ~/.genimg/generations/20260925_115943_ca5e9a.png
dry-run: no API call made.
```

## Codex

- **`--aspect-ratio` is only a request.** genimg adds it to the prompt, so check the result.
- **Runs use your Codex allowance.** genimg's API-equivalent price is for comparison, not a charge.
  See [Codex subscription](../guide/codex-subscription.md).

```console
$ genimg "a lighthouse at dusk" \
    --model codex:image \
    --aspect-ratio 16:9 \
    --dry-run
genimg codex/subscription codex:image → codex:image
  prompt   "a lighthouse at dusk"
  params   n=1 a=16:9
  cost     Codex subscription (usage limits apply)  id=20260925_115944_aa2c84
  runtime  Codex subscription selects the image model and size; aspect ratio is a prompt request.
  output   ~/.genimg/generations/20260925_115944_aa2c84.png
dry-run: no API call made.
```
