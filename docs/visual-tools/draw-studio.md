# Draw Studio

- Sketch on an image and a model redraws it.

Draw Studio is a browser canvas that genimg serves from your own computer.

```bash
genimg draw --model oai:gi2.5 fox-sketch.webp
```

<figure markdown>
  ![Draw Studio with a rough fox doodle on the canvas and the clean fox illustration GPT Image 2.5 made from it in the Generated panel](../assets/draw-studio.webp)
  <figcaption>The command above: the doodle on the canvas and, after a <b>Generate</b> at medium quality (about $0.013), the newest result at the top of the Generated panel.</figcaption>
</figure>

1. Click a source image to put it on the canvas, or draw on a blank one.
2. Mark what you want and describe it in the prompt.
3. **Generate** sends the canvas to the model. Put the result back on the canvas for another pass.

- Results save to `~/.genimg/generations/`; **All** lists earlier ones.
- **codex:image** draws on your [Codex subscription](../guide/codex-subscription.md), no API key.
- `--no-open` prints the URL instead of opening a browser.

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

There is no login: anyone who can reach a `--host` address can generate with your credentials
and open your images. Press Ctrl-C when you finish.

## Draw Studio or the CLI?

| Need | Draw Studio | CLI |
| --- | --- | --- |
| Sketch or annotate | ✅ | Pass a file with `--input` |
| Several variants | One per Generate | `--num` |
| Deliberate diversity | ❌ | `--diverse`, `--deltas` |
| Review grid | Generated panel | `--grid`, `genimg grid` |

## Security boundary

- By default only this computer can reach the Studio.
- With `--host`, anyone who can reach the address can generate, list your generation history, and
  open those images and the ones you loaded. There is no login.
- Your provider keys never reach the page.
- The provider receives your prompt and canvas.

The server binds to `127.0.0.1` or the one `--host` address. It refuses `0.0.0.0`, a Host header
naming anything but a loopback name or that address, and cross-site POSTs.
