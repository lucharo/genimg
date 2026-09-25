# Model-specific options

`--num`, `--diverse`, `--deltas`, `--output` and `--grid` work with every model. The flags below
depend on the model family. genimg rejects a flag the model cannot use before it sends anything,
even on `--dry-run`.

| Flag | Gemini (`gdm:`) | OpenAI (`oai:`) | Codex (`codex:image`) |
| --- | --- | --- | --- |
| `--mode batch` | yes | no | no |
| `--thinking` | `minimal` or `high`, on `gdm:nb2` only | no | no |
| `--quality` | no | `low medium high auto`, plus `xhigh max` on 2.5 | no |
| `--resolution` | by model, see [Models](models.md#gemini) | from the [size table](models.md#openai) | no |
| `--aspect-ratio` | 10 ratios; `gdm:nb2` and `gdm:nb2-lite` add `1:4 4:1 1:8 8:1` | `1:1 4:3 3:4 16:9 9:16`, by resolution | 10 ratios, as a request in the prompt |
| `--input` and reference images | yes | up to 16 PNG, JPEG or WebP files, 50 MB each | yes |
| `--region`, `--project` | yes | no | no |
| `--auth` | no | `azure` or `direct` | no |
| Text from the model | printed, not saved | none | dropped |

## Gemini

`--mode batch` sends one request for all `--num` images. With `--diverse`, the model varies its own
takes. It decides how many images to return, so genimg keeps what arrives and warns when the set
is short. `--deltas` needs the default parallel mode. More in [Diverse images](../guide/diversity.md).

Gemini 3 image models always think before they draw. On `gdm:nb2`, `--thinking` sets how hard:
`minimal` (Google's default) or `high`. Google bills thinking tokens; genimg's estimate leaves
them out.

```console
$ genimg "a minimal fox logo, NOT a grid" --model gdm:nb2 --num 4 --diverse --mode batch --thinking high --dry-run
genimg google/direct gdm:nb2 → gemini-3.1-flash-image
  prompt   "a minimal fox logo, NOT a grid"
  params   n=4 mode=batch diverse thinking=high
  cost     $0.2680 (estimate)  id=20260925_114016_104c51
  outputs  ~/.genimg/generations/20260925_114016_104c51_1.png
           ~/.genimg/generations/20260925_114016_104c51_2.png
           ~/.genimg/generations/20260925_114016_104c51_3.png
           ~/.genimg/generations/20260925_114016_104c51_4.png
  diverse  model-coordinated: the single batched request asks for deliberately different takes
dry-run: no API call made.
```

Every Gemini image model can answer with text as well as images. genimg prints text that arrives
before the image and drops the rest. It saves no text to the metadata sidecar, drops all of it with
`--mode batch`, and does not request the model's thought summaries. A real line from a `gdm:nb2`
run, trimmed:

```text
[genimg/google] model said: Here is the high-fidelity product UI mockup for the
London flight-noise analysis, designed within a precise 12-column fixed grid. I
have integrated …
```

## OpenAI

`--quality` defaults to `medium`. GPT Image 2.5 adds `xhigh` and `max`, and every other model
rejects them. `--input` and reference images go to OpenAI's edits endpoint. `--num` sends separate
requests; genimg rejects `--mode batch` because the takes come back as near-duplicates.

The [Image API](https://developers.openai.com/api/reference/resources/images/methods/generate)
returns images and token counts. It has no text or reasoning output, and its `revised_prompt` field
is for `dall-e-3` only. genimg keeps the image and prices it with its own estimate.

GPT Image 1, 1.5 and 1 mini support only 1024×1024 of genimg's sizes, so leave `--resolution` and
`--aspect-ratio` unset for them.

```console
$ genimg "a lighthouse at dusk" --model oai:gi2.5 --quality xhigh --resolution 2K --aspect-ratio 16:9 --dry-run
genimg openai/direct oai:gpt-image-2.5-sunburst → gpt-image-2.5-sunburst
  prompt   "a lighthouse at dusk"
  params   n=1 q=xhigh r=2K a=16:9 → 2048x1152
  cost     $0.0753 (estimate)  id=20260925_114017_96a2ec
  output   ~/.genimg/generations/20260925_114017_96a2ec.png
dry-run: no API call made.
```

## Codex

Codex picks the model and size. `--aspect-ratio` becomes a line in the prompt, so check the result.
genimg keeps the PNG and ignores Codex's messages. When the image's C2PA manifest names a GPT Image
version, the sidecar records that model for an API-equivalent price range. From a real Codex
sidecar, trimmed:

```json
"model_selection": "runtime",
"aspect_ratio_mode": "prompt",
"dimensions": { "width": 1326, "height": 1186 },
"api_equivalent_cost": { "model_id": "gpt-image-2", "basis": "reported_c2pa_generator" }
```

See [Codex subscription](../guide/codex-subscription.md) for setup and limits.
