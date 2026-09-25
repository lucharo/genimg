# For agents

Your coding agent runs the same `genimg` commands you do. The skills teach it how.

## Install the skills

```bash
npx skills add lucharo/genimg
```

Needs Node.js. The [skills](https://github.com/vercel-labs/skills) CLI asks which agents and
skills to install into this project; add `-g` to install for your user instead.
`npx skills update` refreshes them.

You get the `genimg` skill plus two workflows built on it:
[infographics](skills/genimg-infographic.md) and [image-to-app](skills/image-to-app.md).

## What the `genimg` skill teaches

- Real variation: `-n` with `-d` or `--deltas`, and Gemini batch mode.
- Edit versus reference: `-i` changes an image; images after the prompt steer its style.
- Model and quality choice by task, with logo, icon and favicon recipes.
- Diagrams and infographics, where model choice and prompting differ from illustrations.
- Every flag and its model limits, so the agent never parses `--help`.

## What an agent can read

| Command | Returns |
| --- | --- |
| `genimg auth --json` | which providers are ready |
| `genimg models --json` | which models your credentials list |
| `genimg PROMPT … --dry-run` | model, size, cost and paths, with no API call |
| `genimg history --json` | past generations: prompt, model, paths, cost |
| `genimg grid *.png` | an HTML page for a human to pick from |

Each generation also writes `~/.genimg/metadata/<id>.json` with absolute paths, prompt,
parameters, per-image deltas and cost. Exit code `2` does not prove a request was sent; see
[exit codes](reference/cli.md#exit-codes-and-output).
