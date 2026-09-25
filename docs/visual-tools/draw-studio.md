# Draw Studio

Sketch on an image, then have a model redraw it. Draw Studio is a browser canvas that genimg
serves from your own computer.

```bash
genimg draw -m gdm:nb2 fox-sketch.webp
```

<figure markdown>
  ![Draw Studio with a rough fox doodle on the canvas and a moon sketched beside it](../assets/draw-studio.webp)
  <figcaption>The command above, with the doodle placed on the canvas and a moon added with the pen.</figcaption>
</figure>

1. Click a source image to put it on the canvas, or draw on a blank one.
2. Mark what you want and describe it in the prompt.
3. **Generate** sends the canvas to the model. Put the result back on the canvas for another pass.

Results save to `~/.genimg/generations/`; **All** lists earlier ones. The controls follow the
model. **codex:image** uses your [Codex subscription](../guide/codex-subscription.md) instead
of an API key. `--no-open` prints the URL instead of opening a browser.

## Draw from an iPad

<figure markdown>
  ![Draw Studio in Safari on an iPad, with the fox doodle on the canvas](../assets/draw-studio-ipad.webp){ width="420" }
  <figcaption>The iPad Pro 13-inch simulator, which shares the Mac's localhost. The moon was drawn by touch.</figcaption>
</figure>

| Method | Requires | Pros | Cons |
| --- | --- | --- | --- |
| [Sidecar](https://support.apple.com/en-gb/102597) | Mac and iPad on one Apple Account, within 10 m | Apple Pencil, nothing to install, the Studio stays on `localhost` | The iPad shows the Mac's screen; the Studio ignores pressure |
| [Tailscale](https://tailscale.com/) | Mac and iPad on the same tailnet | Works away from home; only your tailnet can reach it | Needs Tailscale on both |
| Same network | Mac and iPad on one network, such as home Wi-Fi | Nothing to install | Anyone on that network can reach it. Trusted home networks only |

**Sidecar.** Start the Studio as usual, drag the browser window onto the iPad and draw with
Apple Pencil.

```bash
genimg draw
```

**Tailscale.** Serve on the Mac's Tailscale address, then open the printed URL in Safari on the
iPad.

```bash
genimg draw --host "$(tailscale ip -4)"
```

**Same network.** Serve on the Mac's Wi-Fi address (`en0` on most Macs), then open the printed
URL on the iPad.

```bash
genimg draw --host "$(ipconfig getifaddr en0)"
```

Anyone who can reach a `--host` address can generate with your credentials, so press Ctrl-C
when you finish.

## Draw Studio or the CLI?

| Need | Draw Studio | CLI |
| --- | --- | --- |
| Sketch or annotate | Yes | Pass a file with `-i` |
| Several variants | One per Generate | `-n` |
| Deliberate diversity | No | `-d`, `--deltas` |
| Review grid | Generated panel | `-g`, `genimg grid` |

## Security boundary

- The server binds to `127.0.0.1`, or to the one address given with `--host`. It refuses
  `0.0.0.0`, any Host header naming another address, and cross-site POSTs.
- Provider keys stay with genimg; the page never receives them.
- The model runs at the provider, which receives your prompt and canvas.
