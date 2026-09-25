# FAQ

## Can I use my ChatGPT subscription instead of an API key?

Yes. Sign in with `codex login`, then pass `--model codex:image`. Codex picks the image model and size,
so use an API model when you need those controls. See [Codex subscription](guide/codex-subscription.md).

## Why does genimg ask me to choose a model?

Save a default once with `genimg models set-default gdm:nb2`, or pass `--model` each time.
genimg has no built-in default model.

## Where are my images saved?

In `~/.genimg/generations/` unless you pass `--output`. `genimg history` lists them and
`genimg history view` browses them. Each generation also gets a JSON record (prompt, model,
settings, estimated cost) in `~/.genimg/metadata/`.

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

Run `genimg draw` again and open the URL it prints. The tab has probably outlived its local server.

## Why do Draw Studio's controls change with the model?

Each model accepts different sizes, aspect ratios and quality levels. Draw Studio only shows the
controls the selected model accepts. It runs the same `genimg` command you would type, and a test
checks each option it offers, and each aspect and size pair, against the CLI's own validation.

## Can I use Draw Studio from an iPad?

Yes. Sidecar puts the Mac's screen on the iPad, or `genimg draw --host` serves the Studio on the
Mac's Tailscale or Wi-Fi address for Safari. See
[Draw from an iPad](visual-tools/draw-studio.md#draw-from-an-ipad).

## Does Draw Studio work offline? Can I host it?

No to both. It runs on your machine but sends prompts and images to the provider. `--host` shares
your running Studio with your own devices for a session; there is no hosted, multi-user version.

## Does `--num` generate the images one after another?

No. `--num 4` sends four requests in parallel, up to five at a time (two for `codex:image`), so four
images usually take about as long as one, and the ones that succeed are kept if one fails. On Gemini,
`--mode batch` asks for the whole set in one request instead. See
[Diverse images](guide/diversity.md).

## Can an agent run `genimg setup` without a terminal?

Yes. Without a terminal on stdin, `genimg setup` asks nothing: it saves each provider whose key is
already in the environment and passes a free check, and exits `1` if none does. `--model gdm:nb2`
also saves a default. Keys are never passed as arguments. See
[Getting started](getting-started.md).
