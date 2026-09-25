# Choosing a model

Pick by job, then check what each model costs in money and time.

<!-- Charts and the numbers table regenerate from scripts/model_benchmarks.csv with `uv run scripts/model_charts.py`. -->

| Job | Model |
| --- | --- |
| Text, logos, UI | `oai:gi2` |
| Diagrams, arrows, fixed layouts | `gdm:nbp` or `gdm:nb2` |
| Photographic or painterly | `gdm:nbp` |
| Cheap, fast exploration | `gdm:nb2`, or `gdm:nb2-lite` at about 3 s |
| Top benchmark score, time no object | `oai:gi2.5` |

## Quality against cost

![Quality against cost. Best for the price: oai:gi1-mini, gdm:nb2-lite, gdm:nb2, oai:gi2.5.](../assets/charts/cost-quality-light.svg#only-light)
![Quality against cost. Best for the price: oai:gi1-mini, gdm:nb2-lite, gdm:nb2, oai:gi2.5.](../assets/charts/cost-quality-dark.svg#only-dark)

Quality: [Artificial Analysis text-to-image leaderboard](https://artificialanalysis.ai/image/leaderboard/text-to-image),
25 Sep 2026. Cost: genimg's price table at 1024×1024, from [OpenAI](https://developers.openai.com/api/docs/pricing)
and [Gemini API](https://ai.google.dev/gemini-api/docs/pricing) pricing.

Artificial Analysis scores one `--quality` per model. genimg's default, `--quality medium`, is
unscored: $0.013 for `oai:gi2.5` and `oai:gi2.5-flare`, 16 times less than `max`. `--quality auto`
lets OpenAI choose; genimg prices it as `medium`. Every price: [Models](models.md#openai).

## Quality against speed

![Quality against generation time. Fastest for the quality: gdm:nb2-lite, gdm:nb2, oai:gi2.5-flare, oai:gi2.5.](../assets/charts/speed-quality-light.svg#only-light)
![Quality against generation time. Fastest for the quality: gdm:nb2-lite, gdm:nb2, oai:gi2.5-flare, oai:gi2.5.](../assets/charts/speed-quality-dark.svg#only-dark)

Quality and median time for one 1024×1024 image: [Artificial Analysis](https://artificialanalysis.ai/image/models),
25 Sep 2026. It has no time for `oai:gi1` or `oai:gi1-mini`.

??? note "The numbers behind the charts"

    | Model | `--quality` | Cost | Time | Artificial Analysis | Arena |
    | --- | --- | ---: | ---: | ---: | ---: |
    | `oai:gi2.5` | max | $0.211 | 109 s | 1196 (#1) | 1424 (#1) |
    | `oai:gi2.5-flare` | max | $0.211 | 55 s | 1190 (#2) | 1401 (#2) |
    | `oai:gi2` | high | $0.211 | 119 s | 1171 (#3) | 1383 (#3) |
    | `gdm:nb2` |  | $0.067 | 9 s | 1123 (#6) | n/a |
    | `oai:gi1.5` | high | $0.133 | 29 s | 1104 (#8) | n/a |
    | `gdm:nbp` |  | $0.134 | 17 s | 1101 (#11) | 1234 (#16) |
    | `gdm:nb2-lite` |  | $0.034 | 3 s | 1093 (#13) | 1250 (#13) |
    | `oai:gi1` | high | $0.167 | n/a | 1011 (#34) | 1116 (#47) |
    | `oai:gi1-mini` | medium | $0.011 | n/a | 914 (#86) | 1110 (#52) |

    Arena: [text-to-image leaderboard](https://arena.ai/leaderboard/text-to-image), votes to
    24 September. Arena scored `oai:gi2` at `medium` and `gdm:nbp` at 1K, and names no setting for
    the rest. n/a means it lists only a variant genimg does not use. Artificial Analysis scores
    within about ±9 points tie.

## Benchmarks worth checking

- [Arena image edit](https://arena.ai/leaderboard/image-edit), formerly LMArena. People vote
  between two anonymous images.
- [Artificial Analysis image editing](https://artificialanalysis.ai/image/leaderboard/editing),
  and their [methodology](https://artificialanalysis.ai/image/methodology).
