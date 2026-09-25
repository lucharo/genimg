# Input and reference images

An image can go back in two ways. `--input` edits it. A path after the prompt steers a new image.

## Edit an image: `--input`

```bash
genimg "same logo, same style, but at dusk: deep indigo background, warm orange rim light on the fox, keep everything else" \
  --input fox_1.png \
  --model oai:gi2.5-flare
```

<div class="grid" markdown>
![The base fox logo on cream](../assets/fox-1.webp){ width="300" }
![The same fox on indigo with an orange rim light](../assets/fox-dusk.webp){ width="300" }
</div>

The mark, pose and paper-cut style survive. Only what the prompt named changed. To chain edits,
feed the last output back in; `genimg history` records each input.

## Steer with a reference

```bash
genimg "a raccoon character in exactly this paper-cut style and palette, one centred mark" \
  fox_1.png \
  --model oai:gi2.5-flare
```

<div class="grid" markdown>
![The fox logo used as a reference](../assets/fox-1.webp){ width="300" }
![A raccoon in the same paper-cut style](../assets/raccoon-ref.webp){ width="300" }
</div>

A new subject in the reference's style and palette. The reference itself is not edited.

## Both at once

Edit one image and steer it with others. `--dry-run` shows which role each file got:

```console
$ genimg "preserve this room; apply the approved design direction" \
    approved-concept.png palette.png \
    --input original-room.png \
    --model gdm:nb2 \
    --output room-v2.png \
    --dry-run
  input    original-room.png
  refs     #1 approved-concept.png
           #2 palette.png
```

## Provider limits

| Provider | Accepts |
| --- | --- |
| Google Gemini | input and references, any common raster format |
| OpenAI GPT Image | up to 16 images, PNG, JPG or WEBP, 50 MB each |
| Codex | input and references; Codex decides how to use them |

For several views of one subject, edit the same source once per view instead of chaining: each
chained edit drifts further. The [image-to-app](../skills/image-to-app.md) skill works this way.
