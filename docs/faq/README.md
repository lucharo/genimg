# genimg FAQ

Created: 2026-08-13  
Updated: 2026-08-13  
Verified: 2026-08-13

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

The Studio presents the explicit Low, Medium and High choices. Genimg's normal OpenAI
default is Medium, so an additional Auto choice would make the effective setting less clear.
The CLI still accepts `--quality auto` when that provider behavior is wanted.

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

See also [Maintaining the model list](../maintaining-models.md) and
[ADR-0001: No built-in default model](../adr/0001-no-built-in-default-model.md).
