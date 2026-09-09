# Codex subscription generation

## Inside a Codex agent: native tool first

When the agent has `image_gen` available, call it directly, then register its returned
image path with genimg. No second Codex agent is needed:

```bash
genimg history add native.png --prompt "a ceramic blue cube on white" -m codex:image --billing subscription
```

`history add` generates nothing: it copies the original into the genimg archive, reads its
embedded provenance and creates a history sidecar. `-o cube.png` selects a copy destination;
existing files are never overwritten. Add `-i original.png` for edits and repeated
`--ref reference.png` options to record references. The source image is left unchanged.
`--billing` is explicitly declared because an image cannot prove how its generation was paid for.

The native tool is an agent capability exposed by the Codex host, not a public image API
that a standalone CLI can call. Its current inputs are a prompt and image references;
it exposes no image-model or version selector. The `--model` option on `history add` records
the route used; it does not change the image or select a backend version.

## From a terminal or Studio

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
`model_selection: runtime` and `cost_usd_estimated: null`; subscription runs are excluded
from API-spend totals. API routes explicitly record `billing: api`.

## Provenance and theoretical API cost

Each output records its dimensions, SHA-256 and the active embedded C2PA manifest when
available, including creation agents and versions, actions, claim-generator information
and signing information. Extraction uses the C2PA SDK offline; `verification: not_performed`
means the claim and signer have **not** been authenticated. These are reported metadata,
not proof of an API deployment or a guarantee about the next generation.

PNGs with content credentials are preserved byte for byte, including unreadable credential
payloads. Genimg writes its own fields to the sidecar instead of re-saving those PNGs.
Unsigned PNGs retain the existing embedded prompt/parameter behaviour.

`api_equivalent_cost` is a separate theoretical output-image comparison, shown in CLI
results, history details and generation grids. For native outputs reporting `gpt-image`
version `2.0`, genimg infers the comparable API model `gpt-image-2`. Because native quality
is unreported, it uses a **rough low-to-high range**, scaling the reference per-image prices
linearly by pixel area. This approximation excludes prompt/reference input tokens and is
not a quote, measured usage, or subscription charge. Per-output records retain the basis
and assumptions. API routes use their requested model and settings with the existing
coarse estimator. Only delivered images count toward this comparison.

Missing provenance, ambiguous models and models without known prices stay unknown;
genimg does not substitute a documented default or guess which GPT Image 2.5 variant ran.
If any output is unpriced, the generation comparison stays unknown and records its
priced-image coverage. Original claims remain available through `genimg history --json`.

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

The CLI backend makes subscription generation available when the caller has no native
agent tool. Agents with that tool should use the native-first workflow above.
