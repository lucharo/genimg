# Models

Pass `-m` an alias or the provider's model id. `genimg models` lists them with their status for
your credentials, cached for 5 days (`--refresh` probes again); `--aliases` adds the long names.

## Gemini

| Alias | Model id | Cost per image by `-r` | Aspect ratios | `--thinking` |
| --- | --- | --- | --- | --- |
| `gdm:nbp` | [`gemini-3-pro-image`](https://ai.google.dev/gemini-api/docs/models/gemini-3-pro-image) | 1K $0.134 · 2K $0.134 · 4K $0.24 | classic | |
| `gdm:nb2` | [`gemini-3.1-flash-image`](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-image) | 512 $0.045 · 1K $0.067 · 2K $0.101 · 4K $0.151 | extended | `minimal` `high` |
| `gdm:nb2-lite` | [`gemini-3.1-flash-lite-image`](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite-image) | 1K $0.034 | extended | |

- **Classic** aspect ratios: `1:1 2:3 3:2 3:4 4:3 4:5 5:4 9:16 16:9 21:9`. **Extended** adds
  `1:4 4:1 1:8 8:1`.
- Every Gemini model accepts `--mode batch`. Aspect ratio does not change the price.

## OpenAI

| Alias | Model id | Cost per 1K square image by `-q` |
| --- | --- | --- |
| `oai:gi2.5` | [`gpt-image-2.5-sunburst`](https://developers.openai.com/api/docs/models/gpt-image-2.5-sunburst) | low $0.006 · medium $0.013 · high $0.053 · xhigh $0.094 · max $0.211 |
| `oai:gi2.5-flare` | [`gpt-image-2.5-flare`](https://developers.openai.com/api/docs/models/gpt-image-2.5-flare) | low $0.006 · medium $0.013 · high $0.053 · xhigh $0.094 · max $0.211 |
| `oai:gi2` | [`gpt-image-2`](https://developers.openai.com/api/docs/models/gpt-image-2) | low $0.006 · medium $0.053 · high $0.211 |
| `oai:gi1.5` | [`gpt-image-1.5`](https://developers.openai.com/api/docs/models/gpt-image-1.5) | low $0.009 · medium $0.034 · high $0.133 |
| `oai:gi1` | [`gpt-image-1`](https://developers.openai.com/api/docs/models/gpt-image-1) | low $0.011 · medium $0.042 · high $0.167 |
| `oai:gi1-mini` | [`gpt-image-1-mini`](https://developers.openai.com/api/docs/models/gpt-image-1-mini) | low $0.005 · medium $0.011 · high $0.036 |

`-q` defaults to `medium`; `auto` is estimated as `medium`.

Sizes come from one table. Any pair not in it is rejected before the request:

| `-r` | `1:1` | `4:3` / `3:4` | `16:9` / `9:16` |
| --- | --- | --- | --- |
| 1K | 1024×1024 | 1024×768 | |
| 2K | 2048×2048 | 2048×1536 | 2048×1152 |
| 4K | 2880×2880 | | 3840×2160 |

Cost follows pixel count and quality. GPT Image 2 and 2.5 count output tokens the way
OpenAI's calculator does, so a wide 2K image can cost less than a 1K square. The older
models use OpenAI's 1024×1024 per-image price, scaled by pixel area at other sizes.
`--dry-run` prints the estimate for any combination:

```console
$ genimg "a lighthouse at dusk" -m oai:gi2 -r 2K -a 16:9 --dry-run
genimg openai/direct oai:gpt-image-2 → gpt-image-2
  prompt   "a lighthouse at dusk"
  params   n=1 q=medium (default) r=2K a=16:9 → 2048x1152
  cost     $0.0424 (estimate)  id=20260925_093313_0de395
  output   ~/.genimg/generations/20260925_093313_0de395.png
dry-run: no API call made.
```

Estimates exclude text input, under a cent per prompt, and apply to Azure too.
`genimg models --refresh` shows which ids your deployment serves.

## Codex

| Alias | What runs | Controls | Cost |
| --- | --- | --- | --- |
| `codex:image` | [Codex image generation](https://learn.chatgpt.com/docs/image-generation); Codex picks the model and size | `-a` only, as a request in the prompt | Your ChatGPT plan's Codex allowance |

genimg records an API-equivalent price range for Codex runs, for comparison only. See
[Codex subscription](../guide/codex-subscription.md).

## Other ids

An id that is not in the tables still works when its shape is recognised: `gpt-image-*`
goes to OpenAI and `gemini-*-image*` to Google, dated snapshots included. `gdm:imagen4`
errors and points to `gdm:nb2`, because Google retired Imagen 4.

## Prices last checked

| Provider | Source | Checked |
| --- | --- | --- |
| Google | [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing), [Vertex AI pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing) | 25 September 2026 |
| OpenAI | [API pricing](https://developers.openai.com/api/docs/pricing), [image cost calculator](https://developers.openai.com/api/docs/guides/image-generation#calculating-costs) | 24 September 2026 |
| Codex | [Codex pricing](https://learn.chatgpt.com/docs/pricing) | 25 September 2026 |

Prices are estimates. Your bill depends on tier, batch discounts and the exact pixels returned.
