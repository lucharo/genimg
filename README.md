# genimg

Multi-provider image generation CLI. Single command for Gemini (Vertex/direct) and OpenAI (Azure/direct).

## Install

```bash
uv tool install --from . genimg
```

## Use

```bash
genimg "a robot" -o robot.png                    # default model (gdm:nb2)
genimg "a robot" -m oai:gi2 -o robot.png         # OpenAI gpt-image-2
genimg "with refs" --refs a.png b.png -o out.png # reference images
genimg "edit this" -i input.png -o edited.png    # image-to-image
genimg "X" -n 4 -g grid.html                     # batch + HTML grid
genimg models                                    # discover working models
genimg models --refresh                          # re-probe
genimg grid *.png -o g.html --open               # standalone grid
```

## Auth

Auto-detected:
- **Google**: `CLAUDE_GCP_CRED` → Vertex AI; else `GOOGLE_API_KEY`/`GEMINI_API_KEY` → direct
- **OpenAI**: `OPENAI_BASE_URL` containing `azure` → Azure OpenAI; else direct via `OPENAI_API_KEY`

## Models (`-m`)

Aliases: `gdm:nbp` (Pro), `gdm:nb2` (Flash, default), `gdm:nb`, `gdm:imagen4`, `oai:gi2`, `oai:gi1.5`, `oai:gi1`. Bare model IDs also accepted.
