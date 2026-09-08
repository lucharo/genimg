# Codex subscription generation

Use your own ChatGPT login with the local [Codex CLI](https://developers.openai.com/codex/cli/):

```bash
codex login
genimg "a simple black triangle on white" -m codex:image -a 1:1 -o triangle.png
genimg "replace the triangle with an outlined circle" -i triangle.png -m codex:image -o circle.png
```

`genimg auth` checks login readiness. `genimg setup` can enable Codex and offer it as your
default; passing `-m codex:image` works without changing genimg config. API-key-only Codex
logins are rejected. Each person signs in to their own subscription locally.

## Controls and billing

Generation, reference images, edits, numbered variants and prompt deltas use the normal genimg
flags. Each variant starts a separate Codex run, with at most two running concurrently.
Outputs enter the normal genimg history and can be used in Draw Studio.

Codex selects the image model and dimensions. `codex:image` is a backend alias, not a promise
of GPT Image 2.5. `-a` adds an aspect-ratio request to the prompt; inspect the resulting image
when dimensions matter. Quality, resolution, thinking, region, project, API auth overrides and
batch mode are rejected. Incompatible saved quality/resolution defaults are not applied.
For a pinned image model and explicit quality/size controls, use the OpenAI API backend.

Generation consumes your [normal Codex allowance](https://developers.openai.com/codex/image-generation/).
The preview shows subscription billing. Metadata records `billing: subscription`,
`model_selection: runtime` and a null dollar estimate; subscription runs do not add an
invented amount to spend totals.

## Runtime contract

Verified with Codex CLI **0.153.4**: genimg starts `codex exec` with native image generation
enabled, shell execution disabled, a read-only sandbox, an isolated working directory and
ephemeral history. It ignores user CLI config for this child run and removes API-key/endpoint
overrides from the child environment. Your saved login remains owned by Codex. It does not
rewrite your Codex config, extract tokens or fall back to a paid image API.

The CLI currently omits native image-tool events from its JSON stream. Genimg requires a
successful completed turn and exactly one fresh, valid PNG beneath
`$CODEX_HOME/generated_images/<thread-id>/` (default `~/.codex`). The thread ID comes from the
runtime's `thread.started` event. Agent prose is never accepted as an output path, and other
runs' images are never used. Genimg copies the verified PNG to your requested destination;
Codex keeps its original generated file.

A missing tool, refusal, ambiguous output or failed run produces an error. Runs time out after
five minutes, terminate their owned child processes, and are not automatically retried. When
Codex reports a subscription limit, wait for the account allowance to reset or adjust it in
Codex. Updating Codex may change this output contract; an incompatible response fails clearly
instead of reporting a stale image as success.

When already inside a Codex agent with `image_gen` available, call that native tool directly
to avoid starting another agent. This backend makes the same subscription workflow accessible
from genimg and its Studio.
