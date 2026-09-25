# Codex subscription

Generate images with your ChatGPT login through the
[Codex CLI](https://developers.openai.com/codex/cli/). No API key needed.

## Set up

```bash
codex login
genimg auth      # the codex row should show ✓ ChatGPT login
```

`genimg setup` can also make Codex your default. A Codex login that uses an API key does not work.

## Generate

Select it with `-m codex:image`:

```bash
genimg "a simple black triangle on white" -m codex:image -a 1:1 -o triangle.png
genimg "replace the triangle with an outlined circle" -i triangle.png -m codex:image -o circle.png
```

Input and reference images, `-n`, `-d` and `--deltas` work as usual, and every output lands in
`genimg history`.

## What you don't control

Codex picks the image model and size:

```console
$ genimg "a simple black triangle on white" -m codex:image -a 1:1 -o triangle.png --dry-run
genimg codex/subscription codex:image → codex:image
  prompt   "a simple black triangle on white"
  params   n=1 a=1:1
  cost     Codex subscription (usage limits apply)  id=20260925_093120_3583e4
  runtime  Codex subscription selects the image model and size; aspect ratio is a prompt request.
  output   triangle.png
dry-run: no API call made.
```

`-a` only asks for a shape in the prompt, so check the result. genimg rejects `-q`, `-r` and
`--mode batch`. For a pinned model, quality and size, use the OpenAI API (`-m oai:gi2`).

## Cost and limits

Runs use your [Codex allowance](https://developers.openai.com/codex/image-generation/), not API
spend, so `genimg cost` leaves them out. genimg still shows a rough API-equivalent price for
comparison; it is not a charge.

Each variant is its own Codex run, two at a time. A run times out after five minutes and is not
retried. If Codex reports a usage limit, wait for your allowance to reset.
