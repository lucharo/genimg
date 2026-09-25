# Codex subscription

- Images come out of your ChatGPT plan's Codex allowance, not an API bill.
- No API key: sign in to the [Codex CLI](https://developers.openai.com/codex/cli/) with ChatGPT.

## Set up

```bash
codex login
genimg auth      # the codex row should show ✓ ChatGPT login
```

`genimg setup` can also make Codex your default. A Codex login that uses an API key does not work.

## Generate

```bash
genimg "a simple black triangle on white" \
  --model codex:image \
  --aspect-ratio 1:1 \
  --output triangle.png
genimg "replace the triangle with an outlined circle" \
  --input triangle.png \
  --model codex:image \
  --output circle.png
```

Input and reference images, `--num`, `--diverse` and `--deltas` work as usual, and every output
lands in `genimg history`.

## What you don't control

- Codex picks the image model and size. `--aspect-ratio` only asks for a shape in the prompt, so
  check the result.
- For a pinned model, quality and size, use the OpenAI API (`--model oai:gi2`).

```console
$ genimg "a simple black triangle on white" \
    --model codex:image \
    --aspect-ratio 1:1 \
    --output triangle.png \
    --dry-run
genimg codex/subscription codex:image → codex:image
  prompt   "a simple black triangle on white"
  params   n=1 a=1:1
  cost     Codex subscription (usage limits apply)  id=20260925_114052_912a4c
  runtime  Codex subscription selects the image model and size; aspect ratio is a prompt request.
  output   triangle.png
dry-run: no API call made.
```

genimg rejects `--quality`, `--resolution` and `--mode batch` for Codex.

## Cost and limits

- Runs spend your [Codex allowance](https://developers.openai.com/codex/image-generation/), so
  `genimg cost` leaves them out.
- Hit a usage limit? Wait for your allowance to reset.

The API-equivalent price genimg shows is for comparison, not a charge. Each variant is its own
Codex run, two at a time, with a five-minute timeout and no retry.
