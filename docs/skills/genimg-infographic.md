# genimg-infographic

Point your agent at a document or notes; get one publication-ready infographic back.

> Make a 16:9 infographic of `docs/onboarding.md` for a new-hire deck; hand-drawn style.

The skill picks one of 21 layouts (bento grid, funnel…) and one of 22 styles (chalkboard,
subway map…), keeps every number and quote exact, and saves the prompt under `prompts/`.

## Credit

A port of Jim Liu's
[baoyu-infographic](https://github.com/JimLiu/baoyu-skills/tree/main/skills/baoyu-infographic)
(MIT). I first came across baoyu-infographic from PRs in the Hermes repo by Nous Research
([hermes-agent#12254](https://github.com/NousResearch/hermes-agent/pull/12254)). We thank
baoyu-infographic for this skill.

## What changes

| | baoyu-infographic | genimg-infographic |
| --- | --- | --- |
| Layout, style, aspect | recommends, then asks you to confirm | chooses and carries on |
| Renderer | whichever image tool the agent has | genimg, with an explicit model |
| Cost | no preflight | `--dry-run` estimate before a batch |
| Alternatives | one render | named candidates in one `genimg grid` |

[Read the skill](https://github.com/lucharo/genimg/blob/main/skills/genimg-infographic/SKILL.md).
