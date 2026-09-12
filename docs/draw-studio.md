# Draw Studio

Draw Studio is GenIMG's local, pen-friendly canvas. Use it to sketch or annotate an image,
send the flattened canvas to an image-editable model, then put a result back on the canvas for
another pass.

The browser is only a control surface. Generation, provider authentication, files and history all
remain on the Mac running `genimg`.

## Start the Studio

Set up at least one provider first:

```bash
genimg setup
genimg draw
```

Start with existing images by passing files, directories, or both:

```bash
genimg draw diagrams/ reference.png
```

Useful launch options:

```bash
genimg draw -m gdm:nb2       # choose the initial editable model
genimg draw --port 8788      # request a port; GenIMG auto-bumps if it is busy
genimg draw --no-open        # print the URL without opening a browser
```

The Studio exposes the controls supported by the selected model: model, quality, image size,
aspect ratio and thinking. Unsupported controls are hidden. Results are saved under
`~/.genimg/generations/`; switch the Generated panel from **Session** to **All** to browse saved
history and put an earlier result back on the canvas.

Select **codex:image · Codex subscription** to generate with your local Codex ChatGPT login.
Quality and image-size controls are hidden; the cost label shows subscription usage. Codex
selects the image model and dimensions, and aspect ratio is a prompt request.
See [Codex subscription generation](codex-subscription.md) for setup and limits.

## Draw from an iPad

### Sidecar and Apple Pencil

Sidecar is the simplest route when the iPad and Mac are nearby:

1. Run `genimg draw` on the Mac.
2. Connect the iPad from the Mac's **Screen Mirroring** menu, using it as an extended or mirrored
   display.
3. Move the browser window containing Draw Studio to the iPad.
4. Draw with Apple Pencil, then use the Mac or iPad keyboard for longer prompts.

Apple documents the current requirements and controls in
[Use iPad as a second display for your Mac](https://support.apple.com/en-gb/102597). Draw Studio
uses standard pointer events, so Pencil strokes work as pointer input; pressure and Pencil
double-tap are not currently used by the Studio.

### VNC or another remote-screen app

Remote-screen control also works because the browser and server both continue to run on the Mac:

1. On the Mac, enable **System Settings → General → Sharing → Screen Sharing** and restrict access
   to the intended Mac user.
2. Run `genimg draw --no-open` on the Mac and open the exact printed URL in a browser on that Mac.
3. Connect to the Mac from the iPad with a VNC client, then control the Mac browser remotely.
4. When finished, disable Screen Sharing if it is not normally part of your setup.

Apple's [Screen Sharing guide](https://support.apple.com/en-gb/guide/mac-help/mh11848/mac) describes
the Mac setting. Its [iPad VNC example](https://support.apple.com/en-us/125381) shows the same
Mac-to-iPad connection pattern with a touch-panel client. Pencil behaviour and latency depend on
the remote-screen client; unlike Sidecar, VNC is not a drawing-specific input path.

Do not open the printed `localhost` URL directly in Safari on the iPad: there, `localhost` means
the iPad, not the Mac. Draw Studio deliberately listens only on `127.0.0.1` and rejects non-local
Host and Origin headers. Direct LAN or public hosting is not supported.

## Draw Studio and the full CLI are different surfaces

Draw Studio is optimised for spatial iteration. The CLI remains the complete prompt-first surface:

| Need | Draw Studio | CLI |
| --- | --- | --- |
| Sketch or annotate on a canvas | Yes | Use an existing file with `-i` |
| Prompt-generate a first image | Yes | Yes |
| Iterate on a generated result | Put it back on the canvas | Pass it with `-i` or as a reference |
| Generate several variants | One per Generate action | `-n` |
| Deliberate diversity | No | `-d`, `--deltas`, `--mode` |
| Review grid | Generated panel | `-g` or `genimg grid` |
| Collections or reusable style sheets | No | Pass reference files explicitly |
| Provider setup and diagnostics | Readiness is shown | `genimg setup`, `genimg auth`, `genimg models` |

The proposed prompt-first `genimg ui` with collections, runs and the complete CLI control set is
tracked separately in [issue #3](https://github.com/lucharo/genimg/issues/3). It should complement
Draw Studio rather than turn the canvas into a general control panel.

## Security boundary

- Provider credentials stay in the Mac environment or provider tooling; they are not stored in
  browser code.
- The server binds to loopback and checks every request's Host header. Mutating requests also check
  Origin.
- Generated files, metadata and history stay under `~/.genimg/` on the Mac.
- A paid multi-user service would need a separate backend for authentication, server-side provider
  credentials, quotas, storage, abuse controls and billing. The local Studio does not implement
  those concerns.
