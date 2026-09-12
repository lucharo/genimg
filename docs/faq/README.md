# genimg FAQ

Created: 2026-08-13

Updated: 2026-09-12

Verified: 2026-09-12 (new and changed answers; older entries retain their original scope)

## Can genimg generate images using a ChatGPT subscription?

Yes. Run `genimg "your prompt" -m codex:image` after signing in with `codex login`.
Genimg starts the local Codex CLI and automatically saves the generated image's history
record. Your normal Codex allowance applies. See [subscription generation](../codex-subscription.md).

_Created: 2026-09-12 · Updated: 2026-09-12 · Verified: 2026-09-12_

## What is Image Gen, and can genimg call it directly outside Codex?

`image_gen` is an image-generation tool exposed by the agent host. An agent with that tool
can call it directly in its conversation. Standalone genimg accesses it through the local
Codex CLI; it does not expose a separate subscription image API. A host tool call made
outside genimg does not create a genimg history record. See the
[runtime contract](../codex-subscription.md#runtime-contract).

_Created: 2026-09-12 · Updated: 2026-09-12 · Verified: 2026-09-12 · Scope: Codex CLI 0.153.4 integration; recheck after runtime changes_

## Can I select the Image Gen model or version externally?

No model/version selector is exposed through `codex:image`; Codex selects it. Use a named
API model when explicit model, quality and size controls are needed. See
[controls and billing](../codex-subscription.md#controls-and-billing).

_Created: 2026-09-12 · Updated: 2026-09-12 · Verified: 2026-09-12 · Scope: current integration; recheck the host tool schema after upgrades_

## Is GPT Image 2.5 available, including through Image Gen?

Genimg supports `oai:gi2.5` (Sunburst) and `oai:gi2.5-flare` for explicit API requests.
Availability still depends on the account and deployment; a successful generation with
the exact model is the check. `codex:image` does not promise either variant. Embedded
generator/version claims describe the returned image, and cannot establish which model
the next native generation will use. See [model maintenance](../maintaining-models.md)
and [provenance](../codex-subscription.md#provenance-and-theoretical-api-cost).

_Created: 2026-09-12 · Updated: 2026-09-12 · Verified: 2026-09-12 · Scope: genimg catalogue and routing; recheck serving with an exact-model generation_

## What metadata can Image Gen outputs reveal?

When embedded content credentials are present, genimg records the reported generator,
version, actions and signing information alongside dimensions and SHA-256. Credentials
are extracted offline, not signature-verified. Subscription/API billing comes from the
generation route; the theoretical API-cost comparison is separate and remains unknown
when the model or pricing is unknown. See the
[provenance and billing guide](../codex-subscription.md#provenance-and-theoretical-api-cost).

_Created: 2026-09-12 · Updated: 2026-09-12 · Verified: 2026-09-12_

## Is recording part of history, and where is the interactive picker?

Images are added automatically to history when genimg creates them. History is read-only:
`genimg history` lists saved generations, `genimg history view` opens the existing TUI
picker, and `genimg history --json` reads the saved records. There is no manual recording
step. See [generate, then browse](../codex-subscription.md#generate-then-browse).

_Created: 2026-09-12 · Updated: 2026-09-12 · Verified: 2026-09-12_

## What is Studio?

Draw Studio is genimg's local browser canvas for sketching, annotating and iterating on
images. Start it with `genimg draw`; the prompt-first CLI remains available separately.
See the [Draw Studio guide](../draw-studio.md).

_Created: 2026-09-12 · Updated: 2026-09-12 · Verified: 2026-09-12_

## Why can a listed model still fail to generate?

Configured, listed and serving are different states. `genimg models --refresh` refreshes
provider-listing status for genimg's curated models, but only a small generation with the
exact model proves that the current account, endpoint and region can serve it.

## Why can Draw Studio show `Failed to fetch` when authentication is valid?

The browser tab may have outlived its localhost server. Relaunch `genimg draw`, open the
exact URL it prints, then reload or reopen the page. Treat provider authentication as a
separate diagnosis unless the new server returns an authentication error.

## Why do Draw Studio controls change with the selected model?

The providers do not expose one shared parameter set. OpenAI image models use Quality and
a constrained size/aspect matrix; Gemini models expose their own image sizes, aspect ratios
and, for supported models, Thinking. Draw Studio hides controls the selected model cannot use.

## Why is there no OpenAI Quality `Auto` control in Draw Studio?

The Studio presents the selected model's explicit quality choices, including `xhigh`
and `max` for GPT Image 2.5. Genimg's normal OpenAI
default is Medium, so an additional Auto choice would make the effective setting less clear.
The CLI still accepts `--quality auto` when that provider behavior is wanted.

**Correction (2026-09-12):** an earlier version listed only Low, Medium and High;
GPT Image 2.5 also supports `xhigh` and `max`. See [model controls](../draw-studio.md).

_Created: 2026-08-13 · Updated: 2026-09-12 · Verified: 2026-09-12_

## How do I restore or replace the prompt?

Use the Create, Diagram or Polish starter, or choose Default to restore the annotation
instructions. Expanding the prompt lets you edit it directly; the selected starter updates
as the text changes.

## Why is Imagen absent from Draw Studio?

Imagen is text-to-image only in genimg. Draw Studio needs models that can accept the current
canvas as an input for later iterations, so Imagen remains available through the CLI but is
not offered in the Studio model selector.

## Where are Draw Studio results saved?

Generated images are saved under `~/.genimg/generations/`. The Generated panel shows the
current session or the wider saved history, and metadata sidecars are stored under
`~/.genimg/metadata/`.

See also the [Draw Studio guide](../draw-studio.md),
[Maintaining the model list](../maintaining-models.md) and
[ADR-0001: No built-in default model](../adr/0001-no-built-in-default-model.md).
