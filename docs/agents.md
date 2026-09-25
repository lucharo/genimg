# For agents

genimg is built from the bottom up to be human and agent friendly. The CLI is the whole
interface: no daemon, no SDK to learn, `auth`, `models`, `history` and `cost` have a `--json`
form (the other verbs print plain text), and every generation leaves a metadata sidecar an
agent can read back. The bundled **`genimg` skill**
describes the mechanics of the entire package so a coding agent can generate images for you.

## Install the skill into your agent

```bash
genimg skills install            # all bundled skills → Claude Code (~/.claude/skills)
genimg skills install all        # → Claude Code, Codex, Cursor and OpenCode
genimg skills install codex genimg   # one agent, one skill
genimg skills list               # what is linked where
```

Skills are symlinked into each agent's skills directory, so they track the installed genimg.
After `uv tool upgrade genimg`, run `genimg skills update` to refresh the links.

## What the `genimg` skill teaches

The [`genimg` skill](https://github.com/lucharo/genimg/blob/main/skills/genimg/SKILL.md) is
the mechanics layer. It carries the non-obvious patterns that `--help` alone does not make
obvious:

- how to get real variation across candidates (`-n` with `-d`, `--deltas`, or Gemini batch
  mode) and how to show them to a human in a grid;
- edit versus reference: `-i` keeps an image and changes it, positional references steer
  style and layout without being edited;
- model and quality choice by task, including logo, icon and favicon recipes;
- structured diagrams and infographics, where labelled cells and arrows behave differently
  from illustrations;
- a compact table of every flag, its short form and its model constraints, so the agent
  never has to parse `--help`.

## The agent contract

- `genimg auth --json` and `genimg models --json` tell an agent what it can use before it
  spends anything.
- `--dry-run` previews model, size and cost with no API call.
- Human-readable output shows paths as given and may abbreviate the home directory as `~`.
  The metadata sidecar under `~/.genimg/metadata/<id>.json` records absolute output paths,
  prompt, model, parameters, per-image prompt deltas, cost and provenance.
- Exit code `2` alone does not prove a provider request was sent: an unknown option also
  exits `2`, even with `--dry-run`. See [exit codes](reference/cli.md#exit-codes-and-output).
- `genimg history --json` returns the same records; `genimg grid *.png` renders any set of
  images into a shareable HTML review page.

## Layered skills

The `genimg` skill stays mechanical on purpose. Use-case skills sit above it and call it:
[genimg-infographic](skills/genimg-infographic.md), [genimg-agent-refinement](skills/genimg-agent-refinement.md)
and [image-to-app](skills/image-to-app.md). See [Workflow skills](skills/index.md).
