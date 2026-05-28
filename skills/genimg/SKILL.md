---
name: genimg
description: Use the genimg CLI to generate, edit, or batch image outputs with Google Gemini/Imagen or OpenAI image models. Use when the user asks to create, edit, render, make, or generate images, posters, diagrams, visual concepts, or image grids.
---

# genimg

Use `genimg` for image generation. Let the CLI do the explaining when details are needed:

```bash
genimg --help
genimg auth
genimg models
```

## Common Patterns

```bash
# One image, default model.
genimg "a small product photo of a red desk lamp" -o lamp.png

# More candidates plus an HTML grid.
genimg "clean editorial illustration of a sprint planning board" -n 4 -g --open

# Pick a provider/model.
genimg "poster for a late-night jazz set" -m oai:gi2 -o jazz.png
genimg "warm cinematic photo of a mountain cabin" -m gdm:nbp -o cabin.png

# Edit an existing image.
genimg "make it night, keep the same composition" -i cabin.png -o cabin-night.png

# Use reference images after the prompt.
genimg "same palette and line style, new layout" ref1.png ref2.png -o styled.png
```

## Defaults

- Run `genimg setup` if auth is missing.
- Omit `-m` unless the user asks for a specific provider.
- Use `-n 4 -g --open` when exploring options — never run parallel shell jobs as a substitute for `-n N`.
- Use `oai:gi2` when legible in-image text matters.
- Use `gdm:nbp` when quality matters more than speed.
- `-q`/`--quality` is **oai:gi2 only** — silently ignored on gdm models. Omit it unless the model is `oai:gi2`.

Generated images and metadata are archived under `~/.genimg/`.
