# Choosing a model

Which model to reach for, and what it costs you in money and time.

<!-- Charts and table regenerate from scripts/model_benchmarks.csv with `uv run scripts/model_charts.py`. -->

## Quality against cost

![Scatter of quality score against cost per image. Four models sit on the best-for-the-price line: oai:gi1-mini at medium, gdm:nb2-lite, gdm:nb2 and oai:gi2.5 at max. The rest cost more for the same or lower score.](../assets/charts/cost-quality-light.svg#only-light)
![Scatter of quality score against cost per image. Four models sit on the best-for-the-price line: oai:gi1-mini at medium, gdm:nb2-lite, gdm:nb2 and oai:gi2.5 at max. The rest cost more for the same or lower score.](../assets/charts/cost-quality-dark.svg#only-dark)

Circles are Google, squares are OpenAI. The line joins the models that nothing else beats on both
price and score. `oai:gi1.5` and `gdm:nbp` land on the same spot.

OpenAI prices follow `-q`. Artificial Analysis scored GPT Image 2.5 at `max`, which costs $0.211. At
genimg's default `medium` it costs $0.013, but no benchmark has scored that setting yet.

## Quality against speed

![Scatter of quality score against median generation time. gdm:nb2-lite takes about 3 seconds, gdm:nb2 about 9, oai:gi2.5-flare at max about 55 and oai:gi2.5 at max about 109; those four form the fastest-for-the-quality line.](../assets/charts/speed-quality-light.svg#only-light)
![Scatter of quality score against median generation time. gdm:nb2-lite takes about 3 seconds, gdm:nb2 about 9, oai:gi2.5-flare at max about 55 and oai:gi2.5 at max about 109; those four form the fastest-for-the-quality line.](../assets/charts/speed-quality-dark.svg#only-dark)

Median time for one 1024×1024 image. `oai:gi1` and `oai:gi1-mini` are missing because Artificial
Analysis publishes no generation time for them.

## Pick by job

| Job | Model |
| --- | --- |
| Text, logos, UI | `oai:gi2` |
| Diagrams, arrows, fixed layouts | `gdm:nbp` or `gdm:nb2` |
| Photographic or painterly | `gdm:nbp` |
| Cheap, fast exploration | `gdm:nb2`, or `gdm:nb2-lite` at about 3 s |
| Top benchmark score, time no object | `oai:gi2.5` |

??? note "The numbers behind the charts"

    | Model | `-q` | Cost | Time | Artificial Analysis | Arena |
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

    `-q`, cost and time match the Artificial Analysis run. Arena scored `oai:gi2` at `medium` and
    names no setting for the rest. Arena lists `gdm:nb2` only with web search on and `oai:gi1.5`
    only as a "high-fidelity" variant, so neither is mapped. Its `gdm:nbp` score is the 1K entry.
    Artificial Analysis gives each score a 95% margin of about ±9 points, so `oai:gi2.5` and
    `oai:gi2.5-flare` are a statistical tie.

## Sources

Data as of 25 September 2026:

- Quality and time: [Artificial Analysis text-to-image leaderboard](https://artificialanalysis.ai/image/leaderboard/text-to-image)
  and [model comparison](https://artificialanalysis.ai/image/models).
- Second opinion: [Arena text-to-image leaderboard](https://arena.ai/leaderboard/text-to-image), votes to 24 September.
- Cost: genimg's price table at 1024×1024, as `--dry-run` prints it, checked against
  [OpenAI pricing](https://developers.openai.com/api/docs/pricing) and
  [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing). Every size and quality is in [Models](models.md).

## Benchmarks worth checking

- [Arena text-to-image](https://arena.ai/leaderboard/text-to-image) and
  [image edit](https://arena.ai/leaderboard/image-edit). Formerly LMArena. People vote between two
  anonymous images.
- [Artificial Analysis text-to-image](https://artificialanalysis.ai/image/leaderboard/text-to-image)
  and [image editing](https://artificialanalysis.ai/image/leaderboard/editing). Blind votes too, plus
  price and generation time per model. Their [methodology](https://artificialanalysis.ai/image/methodology)
  says how they measure.
