# Models

Pass `-m` an alias or a canonical provider id. `genimg models` shows the same table with a
live listed/missing status for your credentials; `genimg models --aliases` adds every alias.

| Alias | Canonical id | Provider | Resolutions | Quality | Batch | Other aliases |
| --- | --- | --- | --- | --- | --- | --- |
| `gdm:nbp` | `gemini-3-pro-image` | google | 1K 2K 4K | – | yes | `gdm:nano-banana-pro` |
| `gdm:nb2` | `gemini-3.1-flash-image` | google | 512 1K 2K 4K | – | yes | `gdm:nano-banana-2` |
| `gdm:nb2-lite` | `gemini-3.1-flash-lite-image` | google | 1K | – | yes | `gdm:nano-banana-2-lite` |
| `gdm:nb` | `gemini-2.5-flash-image` | google | provider default | – | yes | `gdm:nano-banana` |
| `oai:gi2.5` | `gpt-image-2.5-sunburst` | openai | 1K 2K 4K | low medium high xhigh max auto | – | `oai:gpt-image-2.5-sunburst` |
| `oai:gi2.5-flare` | `gpt-image-2.5-flare` | openai | 1K 2K 4K | low medium high xhigh max auto | – | `oai:gpt-image-2.5-flare` |
| `oai:gi2` | `gpt-image-2` | openai | 1K 2K 4K | low medium high auto | – | `oai:gpt-image-2` |
| `oai:gi1.5` | `gpt-image-1.5` | openai | 1K 2K 4K | low medium high auto | – | `oai:gpt-image-1.5` |
| `oai:gi1` | `gpt-image-1` | openai | 1K 2K 4K | low medium high auto | – | `oai:gpt-image-1` |
| `oai:gi1-mini` | `gpt-image-1-mini` | openai | 1K 2K 4K | low medium high auto | – | `oai:gpt-image-1-mini` |
| `codex:image` | runtime-selected | codex | – | – | – | |

## Aspect ratios

- Gemini 3.1 Flash Image and Flash Lite: `1:1 1:4 1:8 2:3 3:2 3:4 4:1 4:3 4:5 5:4 8:1 9:16 16:9 21:9`.
- Gemini 3 Pro Image and Gemini 2.5 Flash Image: `1:1 2:3 3:2 3:4 4:3 4:5 5:4 9:16 16:9 21:9`.
- GPT Image: `1:1 4:3 3:4` at 1K; `1:1 4:3 3:4 16:9 9:16` at 2K; `1:1 16:9 9:16` at 4K. Each
  pair maps to an exact pixel size (`2K` + `16:9` → 2048×1152), never a substituted ratio.
- Codex: any of the classic ten, as a prompt request; Codex decides the final dimensions.

## Unregistered ids

A model id that is not in the table still works when its shape is recognised: `gpt-image-*`
resolves to OpenAI, `gemini-*-image*` to Google. Dated snapshots such as
`gpt-image-2.5-sunburst-2026-08-01` are accepted directly. `dall-e-*` is not inferred
because the OpenAI provider sends gpt-image-style parameters that DALL-E rejects.

## Retired models

Imagen 4 (`gdm:imagen4`, `-fast`, `-ultra`) was retired by Google on 17 August 2026; the
aliases now error with the replacement (`gdm:nb2`). A saved default pointing at a retired
model is explained rather than silently changed: `genimg models set-default gdm:nb2`.

## Pricing

Estimates are coarse per-image figures from the providers' public rates and are shown as
estimates. GPT Image 2.5 is deliberately unpriced: OpenAI publishes token rates but excludes
2.5 from its per-image calculator, so its cost is recorded as unknown and excluded from
spend totals. Codex subscription runs are billed against your Codex allowance; genimg
records a theoretical API-equivalent range for comparison only.

Availability varies by account and deployment; some ids are api.openai.com only and absent
from a given Azure resource. `genimg models --refresh` re-checks; an exact-model generation
is the only proof that a model serves.
