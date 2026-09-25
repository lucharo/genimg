# FAQ

## Can I use my ChatGPT subscription instead of an API key?

Yes. Sign in with `codex login`, then pass `-m codex:image`. Codex picks the image model and size,
so use an API model when you need those controls. See [Codex subscription](guide/codex-subscription.md).

## Why does genimg ask me to choose a model?

genimg has no built-in default model. Pass `-m`, or save a default with
`genimg models set-default gdm:nb2`.

## Where are my images saved?

Without `-o`, in `~/.genimg/generations/`. Each generation also gets a JSON record (prompt, model,
settings, estimated cost) in `~/.genimg/metadata/`. `genimg history` lists them and
`genimg history view` browses them.

## A model is listed in `genimg models` but fails to generate. Why?

A provider can list a model that your account, endpoint or region cannot serve. Only a small generation
with that exact model proves it works.

## Where did Imagen go?

Google retired the Imagen 4 API on 17 August 2026. Use `gdm:nb2` instead. If Imagen was your saved
default, run `genimg models set-default gdm:nb2`.

## Can I use GPT Image 2.5?

Yes, as `oai:gi2.5` (Sunburst) or `oai:gi2.5-flare`, with an OpenAI or Azure OpenAI key. Whether
your account or deployment serves them varies; `genimg models` shows what it lists.

## Draw Studio says `Failed to fetch`

The browser tab has probably outlived its local server. Run `genimg draw` again and open the URL it
prints.

## Why do Draw Studio's controls change with the model?

Each model accepts different sizes, aspect ratios and quality levels. Draw Studio only shows the
controls the selected model accepts.

## Can I use Draw Studio from an iPad?

Yes, by showing your Mac's screen on the iPad with Sidecar or a screen-sharing app. iPad Safari
cannot open the Mac's `localhost` address. See [Draw Studio](visual-tools/draw-studio.md).

## Does Draw Studio work offline? Can I host it?

No to both. It runs on your machine but sends prompts and images to the provider. There is no hosted,
multi-user version.
