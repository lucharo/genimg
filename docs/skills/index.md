# Workflow skills

genimg ships four skills. One is the mechanics layer; the other three are use-case workflows
that sit above it and call it. Install them into your agent with
`npx skills add lucharo/genimg` (see [For agents](../agents.md)).

| Skill | What it lets you do | Layer |
| --- | --- | --- |
| [`genimg`](https://github.com/lucharo/genimg/blob/main/skills/genimg/SKILL.md) | Generate, edit and vary images with the CLI: variation patterns, edit vs reference, model and quality choice, logo and favicon recipes, structured-diagram rules, the flag table. | mechanics |
| [`genimg-infographic`](genimg-infographic.md) | Turn source material into a publication-ready infographic using 21 information layouts and 22 visual styles, with readable labels and reproducible prompts. | workflow |
| [`genimg-agent-refinement`](genimg-agent-refinement.md) | An optional polish loop: inspect a generated image, name the artifacts, and iterate with edits until it is clean. | workflow |
| [`image-to-app`](image-to-app.md) | Take mockups, wireframes or selected visual directions to a working, visually verified application. | workflow |

Each workflow skill assumes the `genimg` skill is loaded alongside it. They are plain
`SKILL.md` folders (Claude Code, Codex, Cursor and OpenCode all read the same format), so
you can also read them directly and follow the steps by hand.
