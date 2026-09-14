# genimg FAQ

Created: 2026-08-13

Updated: 2026-09-13

Verified: 2026-09-13 (new and changed answers; older entries retain their original scope)

## Can genimg generate images using a ChatGPT subscription?

Yes. Run `genimg "your prompt" -m codex:image` after signing in with `codex login`.
Genimg starts the local Codex CLI and automatically saves the generated image's history
record. Your normal Codex allowance applies. See [subscription generation](guide/codex-subscription.md).

_Created: 2026-09-12 · Updated: 2026-09-12 · Verified: 2026-09-12_

## What is Image Gen, and can genimg call it directly outside Codex?

`image_gen` is an image-generation tool exposed by the agent host. An agent with that tool
can call it directly in its conversation. Standalone genimg accesses it through the local
Codex CLI; it does not expose a separate subscription image API. A host tool call made
outside genimg does not create a genimg history record. See the
[runtime contract](guide/codex-subscription.md#runtime-contract).

_Created: 2026-09-12 · Updated: 2026-09-12 · Verified: 2026-09-12 · Scope: Codex CLI 0.153.4 integration; recheck after runtime changes_

## Can I select the Image Gen model or version externally?

No model/version selector is exposed through `codex:image`; Codex selects it. Use a named
API model when explicit model, quality and size controls are needed. See
[controls and billing](guide/codex-subscription.md#controls-and-billing).

_Created: 2026-09-12 · Updated: 2026-09-12 · Verified: 2026-09-12 · Scope: current integration; recheck the host tool schema after upgrades_

## Is GPT Image 2.5 available, including through Image Gen?

Genimg supports `oai:gi2.5` (Sunburst) and `oai:gi2.5-flare` for explicit API requests.
Availability still depends on the account and deployment; a successful generation with
the exact model is the check. `codex:image` does not promise either variant. Embedded
generator/version claims describe the returned image, and cannot establish which model
the next native generation will use. See [model maintenance](maintainers/maintaining-models.md)
and [provenance](guide/codex-subscription.md#provenance-and-theoretical-api-cost).

_Created: 2026-09-12 · Updated: 2026-09-12 · Verified: 2026-09-12 · Scope: genimg catalogue and routing; recheck serving with an exact-model generation_

## What metadata can Image Gen outputs reveal?

When embedded content credentials are present, genimg records the reported generator,
version, actions and signing information alongside dimensions and SHA-256. Credentials
are extracted offline, not signature-verified. Subscription/API billing comes from the
generation route; the theoretical API-cost comparison is separate and remains unknown
when the model or pricing is unknown. See the
[provenance and billing guide](guide/codex-subscription.md#provenance-and-theoretical-api-cost).

_Created: 2026-09-12 · Updated: 2026-09-12 · Verified: 2026-09-12_

## Is recording part of history, and where is the interactive picker?

Images are added automatically to history when genimg creates them. History is read-only:
`genimg history` lists saved generations, `genimg history view` opens the existing TUI
picker, and `genimg history --json` reads the saved records. There is no manual recording
step. See [generate, then browse](guide/codex-subscription.md#generate-then-browse).

_Created: 2026-09-12 · Updated: 2026-09-12 · Verified: 2026-09-12_

## What is Studio?

Draw Studio is genimg's local browser canvas for sketching, annotating and iterating on
images. Start it with `genimg draw`; the prompt-first CLI remains available separately.
See the [Draw Studio guide](surfaces/draw-studio.md).

_Created: 2026-09-12 · Updated: 2026-09-12 · Verified: 2026-09-12_

## Is there a prompt-first GenIMG UI as well as Draw Studio?

The CLI exposes prompt-first generation controls. The separate GUI concept is tracked in
[issue #3](https://github.com/lucharo/genimg/issues/3); Draw Studio is the implemented,
canvas-focused surface. See the [surface comparison](surfaces/draw-studio.md#draw-studio-and-the-full-cli-are-different-surfaces).

_Created: 2026-09-13 · Updated: 2026-09-13 · Verified: 2026-09-13_

## Can I use Draw Studio from an iPad?

Use the Mac browser through Sidecar or remote-screen control, not the Mac's localhost URL
in iPad Safari. The [iPad guide](surfaces/draw-studio.md#draw-from-an-ipad) documents both routes;
physical Apple Pencil and VNC behaviour still need a real-device check.

_Created: 2026-09-13 · Updated: 2026-09-13 · Verified: 2026-09-13 · Scope: documented setup, not physical-device validation_

## How do users access models, and can Draw Studio be hosted?

Use local provider credentials or the [Codex subscription route](guide/codex-subscription.md).
The host sends prompts and image inputs to remote models: local Studio is not offline.
A public multi-user service is not implemented; it would need a separate backend, not
provider keys embedded in browser code. See the [security boundary](surfaces/draw-studio.md#security-boundary).

_Created: 2026-09-13 · Updated: 2026-09-13 · Verified: 2026-09-13_

## What needs to happen before a release?

Use the [release checklist](https://github.com/lucharo/genimg/issues/2) for scope and status.
Validate the candidate's tests, wheel and source distribution; require green checks on
the exact release-PR head before merging. A green preparation workflow is not publication:
verify the resulting tag, GitHub release and, when publishing to PyPI, indexed files and a
clean install. See the [release workflow](https://github.com/lucharo/genimg/blob/main/.github/workflows/release.yml).

_Created: 2026-09-13 · Updated: 2026-09-14 · Verified: 2026-09-14 · Scope: release gates; consult the live tracker for completion_

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

Auto is now available for OpenAI models. Studio gets its choices from the selected model,
including `xhigh` and `max` for GPT Image 2.5; the default remains Medium. The CLI also
accepts `--quality auto`.

**Correction (2026-09-12):** an earlier version said Studio had no Auto control and listed
only Low, Medium and High. Model-specific controls now include Auto, and GPT Image 2.5
also supports `xhigh` and `max`. See [model controls](surfaces/draw-studio.md).

_Created: 2026-08-13 · Updated: 2026-09-12 · Verified: 2026-09-12_

## How do I restore or replace the prompt?

Use the Create, Diagram or Polish starter, or choose Default to restore the annotation
instructions. Expanding the prompt lets you edit it directly; the selected starter updates
as the text changes.

## Why is Imagen unavailable?

Google shut down the Imagen 4 API models on August 17, 2026. Genimg no longer exposes their
aliases or accepts Imagen model IDs. Use `gdm:nb2` (Gemini 3.1 Flash Image), which supports both
generation and canvas editing.

If an Imagen alias was saved as your default, run `genimg models set-default gdm:nb2`
or `genimg models clear-default`. Reading the old default reports the problem without
silently changing your configuration.

_Created: 2026-08-13 · Updated: 2026-09-13 · Verified: 2026-09-13_

## Where are Draw Studio results saved?

Generated images are saved under `~/.genimg/generations/`. The Generated panel shows the
current session or the wider saved history, and metadata sidecars are stored under
`~/.genimg/metadata/`.

See also the [Draw Studio guide](surfaces/draw-studio.md),
[Maintaining the model list](maintainers/maintaining-models.md) and
[ADR-0001: No built-in default model](maintainers/adr/0001-no-built-in-default-model.md).
